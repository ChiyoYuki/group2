import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from 'react'
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation, useParams, useSearchParams } from 'react-router-dom'
import { ArchiveProvider, useArchive } from './ArchiveContext'
import { cohortName, mediaUrl, projectName, projectPlace, request } from './api'

const MapScene = lazy(() => import('./MapScene'))
const number = value => String(value ?? 0).padStart(2, '0')

function Icon({ name = 'arrow', size = 20, ...props }) {
  const paths = {
    arrow: <><path d="M5 12h14M13 6l6 6-6 6" /></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 4 4" /></>,
    compass: <><circle cx="12" cy="12" r="9" /><path d="m16 8-2.5 5.5L8 16l2.5-5.5L16 8Z" /></>,
    pin: <><path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10" r="2" /></>,
    book: <><path d="M12 5v15M3 4c4-1 6 0 9 2 3-2 5-3 9-2v14c-4-1-6 0-9 2-3-2-5-3-9-2Z" /></>,
    star: <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z" />,
    grid: <><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>,
    timeline: <><path d="M6 3v18M11 6h9M11 12h9M11 18h9" /><circle cx="6" cy="6" r="2" /><circle cx="6" cy="12" r="2" /><circle cx="6" cy="18" r="2" /></>,
    upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 16v5h16v-5" /></>,
    file: <><path d="M14 2H5v20h14V7l-5-5Zm0 0v6h5M8 12h8M8 16h8" /></>,
    check: <path d="m5 12 4 4L19 6" />,
  }
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] || paths.arrow}</svg>
}

function Cover({ path, title, className = '', eager = false }) {
  return <div className={`cover ${className}`}>
    <div className="cover-placeholder" aria-hidden="true"><Icon name="compass" size={44} /><span>FIELD NOTES</span></div>
    {mediaUrl(path) && <img src={mediaUrl(path)} alt={title} loading={eager ? 'eager' : 'lazy'} onError={event => { event.currentTarget.style.display = 'none' }} />}
  </div>
}

function Tags({ project }) {
  return <div className="tags">{project.is_demo && <span className="tag demo">示例</span>}{project.themes.map(theme => <span className="tag" key={theme.id}>{theme.name}</span>)}</div>
}

function Header() {
  return <header className="site-header"><div className="header-inner">
    <Link className="brand" to="/" aria-label="Dream Journey 首页"><span className="brand-mark"><Icon name="compass" size={26} /></span><span>梦想足迹<small>DREAM JOURNEY</small></span></Link>
    <nav aria-label="主导航">
      <NavLink to="/" end>探索地图</NavLink><NavLink to="/projects">项目档案</NavLink><NavLink to="/themes">主题探索</NavLink><NavLink to="/impact">价值与意义</NavLink>
    </nav>
    <Link className="button button-small" to="/contribute"><Icon name="upload" size={15} /><span>分享我的研究</span></Link>
  </div></header>
}

function Footer() {
  return <footer className="site-footer"><Link className="brand" to="/"><Icon name="compass" size={24} /><span>梦想足迹</span></Link><p>带着问题出发，把发现带回来。</p><span>Dream Journey · 学生实地调研档案</span></footer>
}

function PageTitle({ eyebrow, title, children, aside }) {
  return <div className="section-heading"><div><span className="eyebrow">{eyebrow}</span><h2>{title}</h2>{children && <p>{children}</p>}</div>{aside}</div>
}

function LoadState({ children }) {
  const { loading, error, reload } = useArchive()
  if (loading) return <div className="loading-state" role="status"><span className="loader" />正在翻开项目档案…</div>
  if (error) return <div className="empty-state" role="alert"><Icon name="compass" size={36} /><h3>暂时无法读取项目</h3><p>{error}。请确认后端服务已启动。</p><button className="button" onClick={reload}>重新连接</button></div>
  return children
}

function ProjectCard({ project }) {
  return <Link className="project-card" to={`/project/${encodeURIComponent(project.slug)}`}>
    <div className="project-card-image"><Cover path={project.cover_url} title={projectName(project)} />{project.is_featured && <span className="featured-badge"><Icon name="star" size={13} />精选</span>}</div>
    <div className="project-card-body"><Tags project={project} /><h3>{projectName(project)}</h3><p>{project.summary}</p><div className="card-meta"><span><Icon name="pin" size={13} />{projectPlace(project)}</span><span>{cohortName(project)}</span></div><div className="card-link">打开研究档案<Icon size={17} /></div></div>
  </Link>
}

function HomePage() {
  const { projects, loading, error } = useArchive()
  const [selected, setSelected] = useState(null)
  const onSelect = useCallback(region => setSelected(region), [])
  const previews = selected?.projects || [...projects].sort((a, b) => Number(b.is_featured) - Number(a.is_featured)).slice(0, 3)
  const featured = projects.filter(project => project.is_featured).slice(0, 3)
  const recordedLocations = projects.filter(project => project.location && !project.location.includes('示例')).length
  return <>
    <section className="map-hero"><div className="hero-grid">
      <div className="hero-main"><div className="hero-copy"><span className="eyebrow"><span className="live-dot" /> DREAM JOURNEY / 研学档案</span><h1>沿着光点，<br />读一场场<span>田野。</span></h1><p>从一个好奇的问题开始，走进真实的世界。<br />看看同学们如何观察、提问，把发现变成作品。</p><Link to="/projects" className="text-link">寻找下一次出发的灵感<Icon size={18} /></Link></div>
        <Suspense fallback={<div className="map-scene" />}><MapScene projects={projects} onSelect={onSelect} /></Suspense>
        <div className="map-caption"><span className="live-dot" />{recordedLocations ? '光点为有明确地点的项目 · 省级示意位置' : '项目地点待补充，仍可从档案开始探索'}<span className="map-caption-code">01 / EXPLORE</span></div>
      </div>
      <aside className="hero-journal"><div className="journal-heading"><span className="eyebrow">{selected ? 'SELECTED REGION' : 'FROM THE FIELD'}</span><h2>{selected ? selected.name : '一份值得打开的好奇心'}</h2>{selected && <button className="plain-button" onClick={() => setSelected(null)}>查看全部推荐</button>}</div>
        {loading ? <p className="muted">正在读取项目…</p> : error ? <Link to="/projects" className="text-link">连接失败，前往重试<Icon /></Link> : previews.length ? previews.slice(0, 3).map((project, index) => <Link className="journal-card" to={`/project/${project.slug}`} key={project.id}><span className="journal-number">{number(index + 1)}</span><div><div className="journal-meta">{project.is_demo && '示例 · '}{project.themes[0]?.name || '研究记录'}</div><h3>{projectName(project)}</h3><p>{project.summary}</p></div><Cover path={project.cover_url} title={projectName(project)} /></Link>) : <p className="muted">还没有公开项目，期待第一份研究记录。</p>}
        <div className="journal-bottom"><span>每一种好奇，都有自己的方向</span><Icon name="compass" size={28} /></div>
      </aside>
    </div><div className="hero-bottom"><div><span className="large-number">{loading ? '—' : number(projects.length)}</span><span>份公开项目档案</span></div><p>不止抵达远方<br /><span>更要读懂脚下的土地</span></p><a href="#discover" className="scroll-link">继续探索 <span>↓</span></a></div></section>
    <LoadState><section className="section-shell" id="discover"><PageTitle eyebrow="CURATED JOURNEYS / 发现" title={featured.length ? '从这些研究开始' : '看看最近的发现'} aside={<Link className="text-link" to="/projects">全部项目<Icon /></Link>}>问题或许很小，认真寻找答案的过程很大。</PageTitle><div className="project-grid">{(featured.length ? featured : projects.slice(0, 3)).map(project => <ProjectCard key={project.id} project={project} />)}</div>{!projects.length && <EmptyProjects />}</section>
      <TimelineSection compact /><ThemeSection compact /><ImpactSection compact />
    </LoadState>
  </>
}

function EmptyProjects({ reset }) {
  return <div className="empty-state"><Icon name="search" size={36} /><h3>{reset ? '还没有找到这样的项目' : '等待第一份发现'}</h3><p>{reset ? '换一个关键词，或者试试其他主题与届次。' : '公开的研究记录会出现在这里。'}</p>{reset ? <button className="button button-outline" onClick={reset}>清除筛选</button> : <Link className="button" to="/contribute">分享我的研究<Icon /></Link>}</div>
}

function TimelineRows({ projects }) {
  const groups = new Map()
  const sorted = [...projects].sort((a, b) => (b.cohort?.year || 0) - (a.cohort?.year || 0))
  sorted.forEach(project => {
    const key = project.cohort?.name || '届次待补充'
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(project)
  })
  return <div className="timeline">{[...groups].map(([cohort, items]) => <div className="timeline-group" key={cohort}><div className="timeline-label"><span />{cohort}</div><div className="timeline-items">{items.map(project => <Link className="timeline-card" to={`/project/${project.slug}`} key={project.id}><Cover path={project.cover_url} title={projectName(project)} /><div><div className="journal-meta">{project.is_demo && '示例 · '}{project.themes.map(theme => theme.name).join(' / ') || '研究记录'}</div><h3>{projectName(project)}</h3><p>{project.summary}</p></div><Icon /></Link>)}</div></div>)}</div>
}

function TimelineSection({ compact = false }) {
  const { projects } = useArchive()
  return <section className="timeline-section"><div className="section-shell"><PageTitle eyebrow="THROUGH THE YEARS / 历程" title="让每一次出发，都留下回声" aside={<Link className="text-link" to="/projects?view=timeline">浏览时间轴<Icon /></Link>}>沿着届次，回看一份份不断积累的研究记录。未知届次单独保留。</PageTitle><TimelineRows projects={compact ? projects.slice(0, 4) : projects} /></div></section>
}

function ProjectsPage() {
  const { projects, catalog } = useArchive()
  const [params, setParams] = useSearchParams()
  const query = params.get('q') || ''
  const theme = params.get('theme') || ''
  const cohort = params.get('cohort') || ''
  const featured = params.get('featured') === 'true'
  const view = params.get('view') || 'grid'
  const [visible, setVisible] = useState(12)
  function change(name, value) {
    const next = new URLSearchParams(params)
    if (value) next.set(name, value); else next.delete(name)
    setParams(next, { replace: true })
    setVisible(12)
  }
  const filtered = useMemo(() => projects.filter(project =>
    (!query.trim() || [project.title, project.short_title, project.summary, project.location, ...project.themes.map(item => item.name)].filter(Boolean).join(' ').toLocaleLowerCase().includes(query.trim().toLocaleLowerCase())) &&
    (!theme || project.themes.some(item => item.slug === theme)) &&
    (!cohort || project.cohort?.id === cohort) && (!featured || project.is_featured)
  ), [projects, query, theme, cohort, featured])
  return <main className="section-shell archive-page"><PageTitle eyebrow="PROJECT ARCHIVE / 项目档案" title="每一个问题，都是一个起点">找到感兴趣的项目，看看同学们怎样一步步寻找答案。</PageTitle><div className="filter-panel"><label className="search-field"><Icon name="search" /><input aria-label="搜索项目" placeholder="搜索问题、项目或地点…" value={query} onChange={event => change('q', event.target.value)} /></label><label className="select-field"><span>届次</span><select aria-label="筛选届次" value={cohort} onChange={event => change('cohort', event.target.value)}><option value="">全部届次</option>{catalog.cohorts.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="featured-filter"><input type="checkbox" checked={featured} onChange={event => change('featured', event.target.checked ? 'true' : '')} /><Icon name="star" size={16} />只看精选</label></div><div className="theme-chips" aria-label="主题筛选"><button className={!theme ? 'selected' : ''} onClick={() => change('theme', '')}>全部主题</button>{catalog.themes.map(item => <button key={item.id} className={theme === item.slug ? 'selected' : ''} aria-pressed={theme === item.slug} onClick={() => change('theme', item.slug)}>{item.name}</button>)}</div>
    <LoadState><div className="results-toolbar"><p>共 <strong>{filtered.length}</strong> 份项目档案{(query || theme || cohort || featured) && <button className="plain-button" onClick={() => { setParams({}); setVisible(12) }}>清除筛选</button>}</p><div className="view-toggle" aria-label="展示方式"><button title="卡片视图" aria-label="卡片视图" aria-pressed={view !== 'timeline'} className={view !== 'timeline' ? 'selected' : ''} onClick={() => change('view', 'grid')}><Icon name="grid" size={17} /></button><button title="时间轴视图" aria-label="时间轴视图" aria-pressed={view === 'timeline'} className={view === 'timeline' ? 'selected' : ''} onClick={() => change('view', 'timeline')}><Icon name="timeline" size={19} /></button></div></div>
      {!filtered.length ? <EmptyProjects reset={projects.length ? () => { setParams({}); setVisible(12) } : undefined} /> : view === 'timeline' ? <TimelineRows projects={filtered.slice(0, visible)} /> : <div className="project-grid" aria-label="项目列表">{filtered.slice(0, visible).map(project => <ProjectCard key={project.id} project={project} />)}</div>}
      {filtered.length > visible && <div className="load-more"><button className="button button-outline" onClick={() => setVisible(value => value + 12)}>继续翻阅 · 还有 {filtered.length - visible} 份<Icon /></button></div>}
    </LoadState>
  </main>
}

function ThemeSection({ compact = false }) {
  const { projects, catalog } = useArchive()
  const themes = compact ? catalog.themes.filter(theme => projects.some(project => project.themes.some(item => item.id === theme.id))).slice(0, 6) : catalog.themes
  return <section className="section-shell theme-section"><PageTitle eyebrow="FIND YOUR CURIOSITY / 主题" title="世界很大，选一个好奇的方向" aside={compact && <Link className="text-link" to="/themes">所有主题<Icon /></Link>}>从自然到人文，每一种观察，都有值得深挖的故事。</PageTitle><div className="theme-grid">{themes.map((theme, index) => {
    const count = projects.filter(project => project.themes.some(item => item.id === theme.id)).length
    return <Link className="theme-tile" to={`/projects?theme=${encodeURIComponent(theme.slug)}`} key={theme.id}><span className="theme-index">{number(index + 1)} / THEME</span><Icon name={['compass', 'book', 'pin'][index % 3]} size={32} /><div><h3>{theme.name}</h3><p>{count} 份项目档案</p></div><Icon className="theme-arrow" /></Link>
  })}</div>{!themes.length && <p className="muted">主题将随项目资料逐步补充。</p>}</section>
}

function ImpactSection({ compact = false }) {
  const { projects, overview } = useArchive()
  const stats = [
    [projects.length, '公开项目档案'], [new Set(projects.flatMap(project => project.themes.map(theme => theme.id))).size, '个研究主题'],
    [overview?.real_impact.project_count || 0, '个非示例公开项目'], [overview?.real_impact.impact_count || 0, '条真实影响记录'],
  ]
  return <section className="impact-section"><div className="section-shell"><PageTitle eyebrow="BEYOND THE JOURNEY / 价值" title="旅程结束，改变才刚刚开始">把观察变成理解，把理解带回生活。</PageTitle><div className="impact-stats">{stats.map(([count, label]) => <div key={label}><strong>{number(count)}</strong><span>{label}</span></div>)}</div><div className="value-grid">{[
    ['01', '教育价值', '把课堂，搬到现场。', '在真实情境里练习提问、观察和表达，让知识与身边的世界发生联系。', 'book'],
    ['02', '社会连接', '让发现，回到生活。', '倾听不同的声音，理解地方与社区。具体的社会影响，以项目中的证据和出处为准。', 'pin'],
    ['03', '方法启发', '让下一次出发，更有方向。', '一份观察记录、一种访谈方法、一次遇到困难后的调整，都可能成为新的研究起点。', 'compass'],
  ].map(([index, title, lead, body, icon]) => <article className="value-card" key={index}><div className="value-card-top"><span>{index} / VALUE</span><Icon name={icon} size={27} /></div><h3>{title}</h3><h4>{lead}</h4><p>{body}</p></article>)}</div><p className="evidence-note"><Icon name="check" size={16} />示例项目不计入真实影响统计；项目数量不等同于已经证明的社会成效。</p>{!compact && <Link className="button button-outline" to="/projects">去看研究的过程<Icon /></Link>}</div></section>
}

function Resource({ resource }) {
  const url = mediaUrl(resource.resource_url)
  const mime = resource.mime_type || ''
  return <figure className={`resource resource-${mime.split('/')[0] || 'file'}`}>
    <div className="resource-heading"><span><Icon name="file" size={16} />{resource.title}</span>{resource.is_ai_generated && <span className="tag ai">{mime.startsWith('image/') ? 'AI 插画' : mime.startsWith('audio/') ? 'AI 配音' : 'AI 生成'}</span>}</div>
    {mime.startsWith('image/') && url && <a href={url} target="_blank" rel="noreferrer"><img loading="lazy" src={url} alt={resource.alt_text || resource.title} /></a>}
    {mime.startsWith('audio/') && url && <audio controls preload="none" src={url} aria-label={resource.title} />}
    {mime.startsWith('video/') && url && <video controls preload="metadata" src={url} aria-label={resource.title} />}
    {resource.structured_data && <div className="table-scroll"><table><thead><tr>{resource.structured_data.columns.map((column, index) => <th key={index} scope="col">{column}</th>)}</tr></thead><tbody>{resource.structured_data.rows.map((row, index) => <tr key={index}>{row.map((cell, column) => <td key={column}>{cell}</td>)}</tr>)}</tbody></table></div>}
    {resource.content_text && !resource.structured_data && <pre className="resource-text">{resource.content_text}</pre>}
    {(resource.caption || resource.description) && <figcaption>{resource.caption || resource.description}</figcaption>}
    {resource.transcript && <details><summary>展开台词</summary><p className="prose">{resource.transcript}</p></details>}
    {(resource.source_name || resource.creator_credit || resource.provenance_note || resource.rights_note || resource.generation_note) && <details className="source-details"><summary>素材来源与说明</summary><p className="prose">{[resource.source_name, resource.creator_credit, resource.provenance_note, resource.rights_note, resource.generation_note].filter(Boolean).join('\n')}</p>{mediaUrl(resource.source_url) && <a href={mediaUrl(resource.source_url)} target="_blank" rel="noreferrer">查看来源 ↗</a>}</details>}
    {url && <a className="resource-file-link" href={url} target="_blank" rel="noreferrer">打开原始文件 <span>↗</span></a>}
  </figure>
}

function ProjectDetail() {
  const { slug } = useParams()
  const [state, setState] = useState({ slug, project: null, error: '', loading: true })
  const [retry, setRetry] = useState(0)
  useEffect(() => {
    const controller = new AbortController()
    request(`/projects/${encodeURIComponent(slug)}`, { signal: controller.signal }).then(project => setState({ slug, project, error: '', loading: false })).catch(error => {
      if (!controller.signal.aborted) setState({ slug, project: null, error: error.message, loading: false })
    })
    return () => controller.abort()
  }, [slug, retry])
  if (state.slug !== slug || state.loading) return <main className="section-shell loading-state" role="status"><span className="loader" />正在打开研究档案…</main>
  if (state.error) return <main className="section-shell empty-state" role="alert"><h1>暂时无法打开这份档案</h1><p>{state.error}</p><button className="button" onClick={() => { setState(previous => ({ ...previous, loading: true })); setRetry(value => value + 1) }}>重试</button><Link className="text-link" to="/projects">返回项目档案<Icon /></Link></main>
  const project = state.project
  const linked = new Set(project.sections.flatMap(section => section.media.map(link => link.resource.id)))
  const others = project.resources.filter(resource => !linked.has(resource.id))
  return <main className="detail-page"><div className="section-shell"><Link to="/projects" className="back-link">← 返回项目档案</Link><div className="detail-hero"><div><span className="eyebrow">A JOURNEY OF DISCOVERY / 研究档案</span><Tags project={project} /><h1>{project.title}</h1><p className="detail-summary">{project.summary}</p><div className="detail-facts"><span><Icon name="pin" size={16} />{projectPlace(project)}</span><span>{cohortName(project)}</span><span>{project.team_name || '团队待补充'}</span></div></div><Cover path={project.cover_url} title={project.title} eager /></div>
    {project.content_notice && <div className="content-notice"><Icon name="book" size={22} /><p>{project.content_notice}</p></div>}
    <div className="detail-layout"><aside className="detail-toc"><span className="eyebrow">IN THIS JOURNEY</span><a href="#question">从问题出发</a>{project.sections.map((section, index) => <a key={section.id} href={`#section-${section.id}`}><span>{number(index + 1)}</span>{section.title}</a>)}{!project.sections.length && project.journey_entries.length > 0 && <a href="#journey">研究历程</a>}{others.length > 0 && <a href="#resources">成果与资料</a>}<a href="#takeaways">带走一点启发</a>{project.impacts.length > 0 && <a href="#evidence">影响与证据</a>}</aside>
    <div className="detail-content"><section className="detail-block" id="question"><span className="eyebrow">START WITH A QUESTION</span><h2>这次研究，从什么开始？</h2>{project.opening_question && <blockquote>{project.opening_question}</blockquote>}{project.questions.length ? <ol className="question-list">{project.questions.map((question, index) => <li key={index}>{question.topic && <span>{question.topic}</span>}{question.question}</li>)}</ol> : project.research_question && <p className="prose">{project.research_question}</p>}{project.background && <p className="prose">{project.background}</p>}{project.research_methods && <div className="method-box"><span>研究方法</span><p className="prose">{project.research_methods}</p></div>}</section>
      {project.sections.map((section, index) => <section className="detail-block story-section" id={`section-${section.id}`} key={section.id}><div className="story-heading"><span className="step-number">{number(index + 1)}</span><h2>{section.title}</h2></div><p className="prose">{section.body}</p>{section.media.map(link => <div className={link.is_optional ? 'optional-resource' : ''} key={link.resource.id}>{link.is_optional && <span className="tag">可选参考素材</span>}<Resource resource={link.resource} /></div>)}</section>)}
      {!project.sections.length && project.journey_entries.length > 0 && <section className="detail-block" id="journey"><span className="eyebrow">THE RESEARCH PROCESS</span><h2>一步步，走近答案</h2>{project.journey_entries.map((stage, index) => <article className="journey-stage" key={stage.id}><span className="step-number">{number(index + 1)}</span><div><h3>{stage.title}</h3><p className="prose">{stage.description}</p>{[['遇到的挑战', stage.challenges], ['我们的应对', stage.responses], ['回看与反思', stage.reflection]].map(([title, body]) => body && <div key={title}><h4>{title}</h4><p className="prose">{body}</p></div>)}</div></article>)}</section>}
      {others.length > 0 && <section className="detail-block" id="resources"><span className="eyebrow">WHAT WE BROUGHT BACK</span><h2>带回来的作品与资料</h2>{others.map(resource => <Resource resource={resource} key={resource.id} />)}</section>}
      <section className="detail-block takeaways" id="takeaways"><span className="eyebrow">FOR YOUR NEXT JOURNEY</span><h2>给下一次出发的你</h2>{project.learning_outcomes && <><h3>这一次，我们学会了</h3><p className="prose">{project.learning_outcomes}</p></>}{project.practical_tips && <><h3>可以借鉴的小建议</h3><p className="prose">{project.practical_tips}</p></>}{!project.learning_outcomes && !project.practical_tips && <p className="muted">这份档案还未补充学习收获与实践建议。</p>}</section>
      {project.impacts.length > 0 && <section className="detail-block" id="evidence"><span className="eyebrow">IMPACT & EVIDENCE</span><h2>研究留下的改变</h2>{project.is_demo && <p className="tag demo">以下为示例内容，不作为真实影响证据</p>}{project.impacts.map((impact, index) => <article className="impact-evidence" key={index}><h3>{impact.title}</h3><p className="prose">{impact.description}</p>{impact.evidence_reference && <p className="muted">证据出处：{impact.evidence_reference}</p>}{mediaUrl(impact.evidence_url) && <a href={mediaUrl(impact.evidence_url)} target="_blank" rel="noreferrer">查看证据 ↗</a>}</article>)}</section>}
    </div></div><div className="detail-end"><Icon name="compass" size={30} /><p>一个问题的答案，也许是下一个问题的开始。</p><Link className="button button-outline" to="/projects">继续翻阅档案<Icon /></Link></div></div></main>
}

function ContributePage() {
  const { reload } = useArchive()
  const [account, setAccount] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem('journey-account') || 'null') } catch { return null }
  })
  const [mode, setMode] = useState('login')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [published, setPublished] = useState(null)
  const [filename, setFilename] = useState('')
  async function authenticate(event) {
    event.preventDefault()
    const form = event.currentTarget
    setError(''); setBusy(true)
    try {
      const result = await request(`/auth/${mode}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(Object.fromEntries(new FormData(form))) })
      sessionStorage.setItem('journey-account', JSON.stringify(result))
      setAccount(result)
    } catch (error) { setError(error.message) } finally { setBusy(false) }
  }
  async function publish(event) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    const file = data.get('file')
    setError(''); setBusy(true); setPublished(null)
    try {
      const payload = { title: data.get('title'), summary: data.get('summary'), description: data.get('description') }
      if (file?.size) {
        if (file.size > 8 * 1024 * 1024) throw new Error('附件不能超过 8 MB。')
        const content = await new Promise((resolve, reject) => {
          const reader = new FileReader()
          reader.onload = () => resolve(reader.result.split(',', 2)[1])
          reader.onerror = () => reject(new Error('附件读取失败，请重新选择。'))
          reader.readAsDataURL(file)
        })
        payload.file = { name: file.name, content_base64: content }
      }
      const result = await request('/projects', { method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${account.token}` }, body: JSON.stringify(payload) })
      setPublished(result); form.reset(); setFilename(''); reload()
    } catch (error) {
      setError(error.message)
      if (error.status === 401) { setAccount(null); sessionStorage.removeItem('journey-account') }
    } finally { setBusy(false) }
  }
  return <main className="section-shell contribute-page"><div className="contribute-intro"><span className="eyebrow">SHARE YOUR DISCOVERY</span><h1>把你的发现，<br />留给下一个出发的人。</h1><p>从一个问题，到一次观察，再到一份作品。<br />每一段认真研究的过程，都值得被看见。</p><div className="contribute-steps"><span>01 提出问题</span><span>02 记录过程</span><span>03 分享发现</span></div><Icon name="compass" size={100} /></div><div className="form-panel">
    {!account ? <><h2>从这里开始记录</h2><p className="muted">登录后，可分享你的研究与作品。</p><div className="auth-tabs"><button className={mode === 'login' ? 'selected' : ''} onClick={() => { setMode('login'); setError('') }}>登录</button><button className={mode === 'register' ? 'selected' : ''} onClick={() => { setMode('register'); setError('') }}>注册账号</button></div><form onSubmit={authenticate}><label>用户名<input name="username" required minLength={3} maxLength={50} autoComplete="username" placeholder="3—50 个字符，不含空白" /></label><label>密码<input name="password" type="password" required minLength={mode === 'register' ? 8 : 1} maxLength={128} autoComplete={mode === 'register' ? 'new-password' : 'current-password'} placeholder={mode === 'register' ? '至少 8 个字符' : '输入你的密码'} /></label><button className="button" disabled={busy}>{busy ? '正在处理…' : mode === 'login' ? '登录，开始分享' : '创建账号'}<Icon /></button></form></> : <><div className="account-bar"><span>你好，{account.user.username}</span><button className="plain-button" onClick={() => { setAccount(null); sessionStorage.removeItem('journey-account'); setError(''); setPublished(null) }}>退出账号</button></div><h2>分享一份研究记录</h2><p className="publish-notice">提交后会立即公开，请确认正文与附件可以公开分享。</p><form onSubmit={publish}><label>项目标题<input name="title" placeholder="用一句话说说你的研究" maxLength={200} required /></label><label>项目简介<textarea name="summary" placeholder="你研究了什么，又发现了什么？" maxLength={2000} required rows={3} /></label><label>研究过程与说明 <span>选填</span><textarea name="description" placeholder="记录问题、观察方法、遇到的困难和新的发现…" rows={5} maxLength={20000} /></label><label className="file-upload"><Icon name="upload" size={26} /><strong>{filename || '添加一份作品或过程记录'}</strong><span>图片、音视频、TXT、Markdown 或 CSV · 最大 8 MB</span><input type="file" name="file" aria-label="上传附件" accept=".jpg,.jpeg,.png,.webp,.mp3,.wav,.ogg,.mp4,.webm,.txt,.md,.csv" onChange={event => setFilename(event.target.files[0]?.name || '')} /></label><button className="button" disabled={busy}>{busy ? '正在发布…' : '公开分享这份研究'}<Icon /></button></form>{published && <div className="publish-success" role="status"><Icon name="check" /><span>“{published.title}”已发布。<Link to={`/project/${published.slug}`}>打开我的研究档案 ↗</Link></span></div>}</>}
    {error && <p className="form-error" role="alert">{error}</p>}
  </div></main>
}

function ScrollReset() {
  const location = useLocation()
  useEffect(() => {
    if (location.hash) {
      const frame = requestAnimationFrame(() => document.getElementById(location.hash.slice(1))?.scrollIntoView())
      return () => cancelAnimationFrame(frame)
    }
    window.scrollTo(0, 0)
    document.title = location.pathname.startsWith('/project/') ? '研究档案 · 梦想足迹' : '梦想足迹 · Dream Journey'
  }, [location.pathname, location.hash])
  return null
}

export default function App() {
  return <BrowserRouter><ArchiveProvider><ScrollReset /><a className="skip-link" href="#main-content">跳到主要内容</a><Header /><div id="main-content"><Routes><Route path="/" element={<HomePage />} /><Route path="/projects" element={<ProjectsPage />} /><Route path="/project/:slug" element={<ProjectDetail />} /><Route path="/themes" element={<LoadState><ThemeSection /></LoadState>} /><Route path="/impact" element={<LoadState><ImpactSection /></LoadState>} /><Route path="/contribute" element={<ContributePage />} /><Route path="*" element={<main className="section-shell empty-state"><h1>这条路还没有留下足迹</h1><Link className="button" to="/">返回首页<Icon /></Link></main>} /></Routes></div><Footer /></ArchiveProvider></BrowserRouter>
}
