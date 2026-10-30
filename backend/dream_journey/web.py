"""Versioned API, account registration, project upload and media delivery."""

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from dataclasses import asdict
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import SQLAlchemyError

from dream_journey.database import make_engine, make_session_factory, transaction
from dream_journey.models import AuthSession, ResourceType, User, utc_now
from dream_journey.repositories import CatalogRepository, ProjectRepository
from dream_journey.serializers import project_card, project_detail
from dream_journey.services import ProjectService

BACKEND = Path(__file__).resolve().parents[1]
MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".md": "text/markdown; charset=utf-8",
    ".csv": "text/csv; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/favicon.svg": ("favicon.svg", "image/svg+xml"),
}
MAX_JSON_BODY = 12 * 1024 * 1024
MAX_UPLOAD_SIZE = 8 * 1024 * 1024


class APIError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _hash_password(password: str) -> str:
    iterations = 600_000
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return "$".join(
        (
            "pbkdf2_sha256",
            str(iterations),
            base64.urlsafe_b64encode(salt).decode(),
            base64.urlsafe_b64encode(digest).decode(),
        )
    )


def _password_matches(password: str, stored: str) -> bool:
    try:
        algorithm, iterations, salt, expected = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            base64.urlsafe_b64decode(salt),
            int(iterations),
        )
    except (ValueError, binascii.Error):
        return False
    return hmac.compare_digest(base64.urlsafe_b64encode(digest).decode(), expected)


def _issue_token(session, user: User) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    expires_at = utc_now() + timedelta(days=7)
    session.add(
        AuthSession(
            user_id=user.id,
            token_digest=hashlib.sha256(token.encode()).hexdigest(),
            expires_at=expires_at,
        )
    )
    session.flush()
    return token, expires_at.isoformat()


class ArchiveServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        engine: Engine,
        *,
        cors_origins=None,
        media_root=None,
        static_root=None,
        mounts=None,
    ):
        self.session_factory = make_session_factory(engine)
        self.media_root = Path(
            media_root or os.getenv("MEDIA_ROOT", str(BACKEND / "media"))
        ).resolve()
        self.static_root = Path(static_root).resolve() if static_root is not None else None
        self.mounts = {
            prefix.rstrip("/"): Path(root).resolve() for prefix, root in (mounts or {}).items()
        }
        self.cors_origins = set(
            cors_origins
            if cors_origins is not None
            else filter(
                None, (item.strip() for item in os.getenv("CORS_ALLOWED_ORIGINS", "").split(","))
            )
        )
        super().__init__(address, ArchiveHandler)


class ArchiveHandler(BaseHTTPRequestHandler):
    server: ArchiveServer

    def _cors(self) -> None:
        origin = self.headers.get("Origin")
        if origin and (origin in self.server.cors_origins or "*" in self.server.cors_origins):
            self.send_header(
                "Access-Control-Allow-Origin", "*" if "*" in self.server.cors_origins else origin
            )
            self.send_header(
                "Access-Control-Expose-Headers", "Content-Range, Accept-Ranges, Content-Length"
            )
        self.send_header("Vary", "Origin")

    def _send(self, status: int, body: bytes, content_type: str, *, head=False, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def _json(self, status, data, *, head=False):
        self._send(
            status,
            json.dumps(data, ensure_ascii=False).encode(),
            "application/json; charset=utf-8",
            head=head,
        )

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        if (
            origin
            and origin not in self.server.cors_origins
            and "*" not in self.server.cors_origins
        ):
            self._json(403, {"error": "Origin is not allowed"})
            return
        self._send(
            204,
            b"",
            "text/plain",
            headers={
                "Access-Control-Allow-Methods": "GET, HEAD, POST, OPTIONS",
                "Access-Control-Allow-Headers": "Accept, Authorization, Content-Type, Range",
            },
        )

    def _read_json(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as error:
            raise APIError(400, "请求长度不正确。") from error
        if length <= 0:
            raise APIError(400, "请求内容不能为空。")
        if length > MAX_JSON_BODY:
            raise APIError(413, "请求内容过大。")
        try:
            data = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise APIError(400, "请求必须是有效的 JSON。") from error
        if not isinstance(data, dict):
            raise APIError(400, "请求必须是 JSON 对象。")
        return data

    def _current_user(self, session) -> User | None:
        authorization = self.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return None
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            return None
        digest = hashlib.sha256(token.encode()).hexdigest()
        return session.scalar(
            select(User)
            .join(AuthSession, AuthSession.user_id == User.id)
            .where(AuthSession.token_digest == digest, AuthSession.expires_at > utc_now())
        )

    def _require_user(self, session) -> User:
        user = self._current_user(session)
        if user is None:
            raise APIError(401, "请先登录。")
        return user

    def do_POST(self):
        try:
            self._post()
        except APIError as error:
            self._json(error.status, {"error": error.message})
        except (ValueError, TypeError, OverflowError):
            self._json(400, {"error": "请求参数不正确。"})
        except SQLAlchemyError:
            self.log_error("Database request failed; check migrations and DATABASE_URL")
            self._json(503, {"error": "数据库暂时不可用，请确认已完成初始化。"})
        except OSError:
            self.log_error("Upload failed")
            self._json(500, {"error": "文件保存失败。"})

    def _post(self):
        path = unquote(urlsplit(self.path).path)
        if path.startswith("/api/v1/"):
            path = "/api/" + path.removeprefix("/api/v1/")
        if path not in {"/api/auth/register", "/api/auth/login", "/api/projects"}:
            self._json(404, {"error": "接口不存在。"})
            return
        data = self._read_json()
        status = 200
        written_file = None
        try:
            with transaction(self.server.session_factory) as session:
                if path == "/api/auth/register":
                    username = data.get("username", "")
                    password = data.get("password", "")
                    if not isinstance(username, str):
                        raise APIError(400, "用户名必须是文本。")
                    username = username.strip().lower()
                    if (
                        len(username) < 3
                        or len(username) > 50
                        or any(character.isspace() for character in username)
                    ):
                        raise APIError(400, "用户名需为 3—50 个字符，且不能包含空白。")
                    if not isinstance(password, str) or not 8 <= len(password) <= 128:
                        raise APIError(400, "密码长度需为 8—128 个字符。")
                    if session.scalar(select(User).where(User.username == username)) is not None:
                        raise APIError(409, "用户名已注册。")
                    user = User(username=username, password_hash=_hash_password(password))
                    session.add(user)
                    session.flush()
                    token, expires_at = _issue_token(session, user)
                    result = {
                        "token": token,
                        "expires_at": expires_at,
                        "user": {"id": str(user.id), "username": user.username},
                    }
                    status = 201
                elif path == "/api/auth/login":
                    username = data.get("username", "")
                    password = data.get("password", "")
                    if not isinstance(username, str) or not isinstance(password, str):
                        raise APIError(400, "用户名和密码必须是文本。")
                    user = session.scalar(
                        select(User).where(User.username == username.strip().lower())
                    )
                    if user is None or not _password_matches(password, user.password_hash):
                        raise APIError(401, "用户名或密码错误。")
                    token, expires_at = _issue_token(session, user)
                    result = {
                        "token": token,
                        "expires_at": expires_at,
                        "user": {"id": str(user.id), "username": user.username},
                    }
                else:
                    user = self._require_user(session)
                    title = data.get("title", "")
                    summary = data.get("summary", "")
                    description = data.get("description", "")
                    if not isinstance(title, str) or not title.strip() or len(title) > 200:
                        raise APIError(400, "项目标题不能为空，且不能超过 200 个字符。")
                    if not isinstance(summary, str) or not summary.strip() or len(summary) > 2000:
                        raise APIError(400, "项目简介不能为空，且不能超过 2000 个字符。")
                    if not isinstance(description, str) or len(description) > 20_000:
                        raise APIError(400, "项目说明不能超过 20000 个字符。")
                    upload = data.get("file")
                    content = None
                    filename = None
                    suffix = None
                    if upload is not None:
                        if not isinstance(upload, dict):
                            raise APIError(400, "附件格式不正确。")
                        filename = upload.get("name", "")
                        encoded = upload.get("content_base64", "")
                        if (
                            not isinstance(filename, str)
                            or not filename.strip()
                            or len(filename) > 200
                            or not isinstance(encoded, str)
                        ):
                            raise APIError(400, "附件名称或内容不正确。")
                        filename = filename.strip()
                        suffix = Path(filename).suffix.lower()
                        if suffix not in MEDIA_TYPES:
                            raise APIError(400, "暂不支持此附件类型。")
                        try:
                            content = base64.b64decode(encoded, validate=True)
                        except binascii.Error as error:
                            raise APIError(400, "附件内容不是有效的 Base64。") from error
                        if not content or len(content) > MAX_UPLOAD_SIZE:
                            raise APIError(400, "附件不能为空，且不能超过 8 MB。")
                    service = ProjectService(session)
                    slug = f"user-{uuid.uuid4().hex}"
                    project = service.create_draft(
                        title=title.strip(),
                        slug=slug,
                        summary=summary.strip(),
                        background=description.strip(),
                        content_kind="documented",
                        is_demo=False,
                    )
                    project.owner_id = user.id
                    resource_url = None
                    if content is not None:
                        resource_type = session.scalar(
                            select(ResourceType).where(ResourceType.code == "user-upload")
                        )
                        if resource_type is None:
                            resource_type = ResourceType(code="user-upload", name="用户上传")
                            session.add(resource_type)
                            session.flush()
                        relative_path = (
                            Path("uploads") / str(project.id) / f"{uuid.uuid4().hex}{suffix}"
                        )
                        file_path = (self.server.media_root / relative_path).resolve()
                        if not file_path.is_relative_to(self.server.media_root):
                            raise APIError(400, "附件路径不正确。")
                        written_file = file_path
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        with file_path.open("xb") as stream:
                            stream.write(content)
                        resource_url = "/media/" + relative_path.as_posix()
                        service.add_resource(
                            project.id,
                            resource_type_id=resource_type.id,
                            title=filename,
                            resource_url=resource_url,
                            mime_type=MEDIA_TYPES[suffix].split(";", 1)[0],
                            source_name=user.username,
                            file_size_bytes=len(content),
                            sha256=hashlib.sha256(content).hexdigest(),
                        )
                    project.status = "published"
                    project.published_at = utc_now()
                    session.flush()
                    result = {
                        "id": str(project.id),
                        "slug": project.slug,
                        "title": project.title,
                        "status": project.status,
                        "resource_url": resource_url,
                    }
                    status = 201
        except Exception:
            if written_file is not None:
                written_file.unlink(missing_ok=True)
            raise
        self._json(status, result)

    def do_GET(self):
        try:
            self._get()
        except (BrokenPipeError, ConnectionResetError):
            pass  # Media players may cancel a request before seeking to another range.

    def do_HEAD(self):
        self._get(head=True)

    def _get(self, *, head=False):
        url = urlsplit(self.path)
        path = unquote(url.path)
        if path.startswith("/api/v1/"):
            path = "/api/" + path.removeprefix("/api/v1/")
        if path.startswith("/api/"):
            try:
                with transaction(self.server.session_factory) as session:
                    repository = ProjectRepository(session)
                    catalog = CatalogRepository(session)
                    if path == "/api/health":
                        result = {
                            "status": "ok",
                            "api_version": 1,
                            "database_revision": session.scalar(
                                text("SELECT version_num FROM alembic_version")
                            ),
                        }
                    elif path == "/api/catalog":
                        result = {
                            "themes": [
                                {"id": str(t.id), "name": t.name, "slug": t.slug}
                                for t in catalog.list_themes()
                            ],
                            "cohorts": [
                                {"id": str(c.id), "name": c.name, "year": c.year}
                                for c in catalog.list_cohorts()
                            ],
                            "resource_types": [
                                {"code": t.code, "name": t.name}
                                for t in catalog.list_resource_types()
                            ],
                        }
                    elif path == "/api/overview":
                        result = {
                            "published_projects": repository.list_public(page_size=1).total,
                            "real_impact": asdict(repository.real_impact_overview()),
                        }
                    elif path == "/api/projects":
                        query = {key: values[-1] for key, values in parse_qs(url.query).items()}
                        featured = query.get("featured", "false")
                        if featured not in {"true", "false"}:
                            raise ValueError("featured must be true or false")
                        page = repository.list_public(
                            dataset_key=query.get("dataset"),
                            cohort_id=uuid.UUID(query["cohort"]) if query.get("cohort") else None,
                            theme_slug=query.get("theme"),
                            keyword=query.get("q"),
                            featured_only=featured == "true",
                            page=int(query.get("page", "1")),
                            page_size=int(query.get("page_size", "12")),
                        )
                        result = {
                            "items": [project_card(item) for item in page.items],
                            "total": page.total,
                            "page": page.page,
                            "page_size": page.page_size,
                        }
                    elif path.startswith("/api/projects/"):
                        slug = path.removeprefix("/api/projects/")
                        sections_only = slug.endswith("/sections")
                        if sections_only:
                            slug = slug.removesuffix("/sections")
                        project = repository.get_public_by_slug(slug)
                        if project is None:
                            self._json(404, {"error": "项目不存在或尚未公开。"}, head=head)
                            return
                        result = project_detail(project)
                        if sections_only:
                            result = {
                                "project_id": result["id"],
                                "slug": slug,
                                "sections": result["sections"],
                            }
                    else:
                        self._json(404, {"error": "接口不存在。"}, head=head)
                        return
                self._json(200, result, head=head)
            except (ValueError, TypeError, OverflowError):
                self._json(400, {"error": "筛选或分页参数不正确。"}, head=head)
            except SQLAlchemyError:
                self.log_error("Database request failed; check migrations and DATABASE_URL")
                self._json(503, {"error": "数据库暂时不可用，请确认已完成初始化。"}, head=head)
            return
        if path in STATIC_FILES and self.server.static_root is not None:
            filename, content_type = STATIC_FILES[path]
            file = self.server.static_root / filename
        elif path.startswith("/media/"):
            directory = self.server.media_root
            file = (directory / path.removeprefix("/media/")).resolve()
            if not file.is_relative_to(directory) or file.suffix.lower() not in MEDIA_TYPES:
                self._json(404, {"error": "媒体不存在。"}, head=head)
                return
            content_type = MEDIA_TYPES[file.suffix.lower()]
        else:
            match = next(
                (
                    (prefix, root)
                    for prefix, root in self.server.mounts.items()
                    if path.startswith(prefix + "/")
                ),
                None,
            )
            if match is None:
                self._json(404, {"error": "页面不存在。"}, head=head)
                return
            prefix, directory = match
            file = (directory / path.removeprefix(prefix + "/")).resolve()
            if not file.is_relative_to(directory) or file.suffix.lower() not in MEDIA_TYPES:
                self._json(404, {"error": "资源不存在。"}, head=head)
                return
            content_type = MEDIA_TYPES[file.suffix.lower()]
        if not file.is_file():
            self._json(404, {"error": "资源不存在。"}, head=head)
            return
        self._file(file, content_type, head=head)

    def _file(self, file: Path, content_type: str, *, head=False):
        size = file.stat().st_size
        start, end = 0, size - 1
        range_header = self.headers.get("Range") if not head else None
        if range_header:
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header.strip())
            try:
                if not match or not any(match.groups()) or size == 0:
                    raise ValueError("Invalid range")
                left, right = match.groups()
                if left:
                    start = int(left)
                    end = min(int(right), size - 1) if right else size - 1
                else:
                    suffix = int(right)
                    if suffix <= 0:
                        raise ValueError("Invalid suffix")
                    start = max(0, size - suffix)
                if start > end or start >= size:
                    raise ValueError("Unsatisfiable range")
            except ValueError:
                self._send(
                    416,
                    b"",
                    content_type,
                    head=head,
                    headers={"Content-Range": f"bytes */{size}", "Accept-Ranges": "bytes"},
                )
                return
        self.send_response(206 if range_header else 200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(max(0, end - start + 1)))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        if range_header:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        if not head:
            with file.open("rb") as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining > 0:
                    chunk = stream.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)


def initialize_database(engine: Engine):
    config = Config(str(BACKEND / "alembic.ini"))
    with engine.connect() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--migrate", action="store_true", help="Apply schema migrations without importing content"
    )
    parser.add_argument(
        "--media-root",
        type=Path,
        help="Local media directory; defaults to MEDIA_ROOT or backend/media",
    )
    parser.add_argument("--static-dir", type=Path, help="Optional test client directory")
    parser.add_argument(
        "--mount",
        action="append",
        default=[],
        metavar="URL_PREFIX=DIRECTORY",
        help="Optional additional media mount",
    )
    parser.add_argument(
        "--cors-origin", action="append", help="Allowed frontend Origin; repeat to allow more"
    )
    args = parser.parse_args()
    mounts = {}
    for item in args.mount:
        prefix, separator, directory = item.partition("=")
        if (
            not separator
            or not prefix.startswith("/")
            or prefix in {"/", "/api", "/media"}
            or ".." in prefix.split("/")
            or not directory
        ):
            parser.error("--mount must use /url-prefix=directory")
        mounts[prefix] = Path(directory)
    engine = make_engine(
        os.environ.get("DATABASE_URL", f"sqlite:///{BACKEND / 'dream_journey.db'}")
    )
    try:
        if args.migrate:
            initialize_database(engine)
        with ArchiveServer(
            (args.host, args.port),
            engine,
            cors_origins=args.cors_origin,
            media_root=args.media_root,
            static_root=args.static_dir,
            mounts=mounts,
        ) as server:
            print(f"Dream Journey API: http://{args.host}:{server.server_port}", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
