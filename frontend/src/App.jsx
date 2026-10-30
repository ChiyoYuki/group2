import { useEffect, useMemo, useRef, useState } from 'react'
import { BrowserRouter, Routes, Route, Link, useNavigate, useParams } from 'react-router-dom'
import * as echarts from 'echarts'
import { projectDetails } from './projectDetails'

// —— 项目数据（来自三个图文配音素材包）
const projects = [
  {
    slug: 'dangaer-ancient-city',
    city: '湟源', lng: 101.2711, lat: 36.6826, year: 2026,
    title: '古城里的马，也要“吃饭”吗？',
    theme: '历史文化', cohort: '去远方 项目',
    summary: '从“马也进去吃饭吗”这个问题出发，寻找丹噶尔古城里做生意、歇脚和交流文化的线索。',
    image: '/projects/dangaer/cover.png',
  },
  {
    slug: 'miao-embroidery-culture',
    city: '贵州', lng: 106.6302, lat: 26.6646, year: 2026,
    title: '用针线传承的民族文化',
    theme: '民族文化', cohort: '去远方 项目',
    summary: '从“苗族衣服上的花纹是怎么做出来的”这个问题出发，了解苗绣、银饰和蜡染，把发现画成一张手抄报。',
    image: '/projects/miao/cover.png',
  },
  {
    slug: 'nanjing-plane-trees',
    city: '南京', lng: 118.7969, lat: 32.0603, year: 2026,
    title: '梧桐把马路盖成“山洞”了吗？',
    theme: '自然观察', cohort: '去远方 项目',
    summary: '从一张林荫道路照片出发，看看树枝和叶子怎样把路变成绿色的“山洞”。',
    image: '/projects/nanjing/cover.png',
  },
]

const CARD_W = 250
const CARD_H = 92
const CARD_GAP = 14
const EDGE = 44

// 每个城市「大图→飞入」一个循环的时长（毫秒）
const CYCLE_MS = 1150

// 主题说明（第 3 屏用）
const THEME_DESC = {
  历史文化: '古城、商路与历史的想象力',
  民族文化: '苗绣、银饰与蜡染手艺',
  自然观察: '行道树、树冠与城市里的自然',
  文化: '城市记忆、口述史与日常生活',
  文化遗产: '保护、修复与再使用',
  生态: '湿地、水系与生物多样性',
  建筑: '空间、材料与在地营造',
  农业: '耕作、灌溉与乡村协作',
  社区研究: '公共空间与居民参与',
  博物馆: '展陈、教育与公众参与',
  经济: '产业、生计与地方发展',
}

// 价值卡片（第 4 屏用）
const VALUE_ITEMS = [
  {
    label: 'Educational',
    title: '教育价值',
    lead: '把好奇变成问题',
    desc: '学生从一个自己的问题出发，经历观察、查资料、动手做和表达，学会自己寻找答案。',
  },
  {
    label: 'Social',
    title: '社会影响',
    lead: '让发现被更多人听见',
    desc: '发现卡、手抄报和配音故事把学习成果分享出去，也留下可继续追问的线索。',
  },
  {
    label: 'Method',
    title: '方法价值',
    lead: '可复用的探究流程',
    desc: '先提问、再观察、查资料、分清事实与猜想——一套小学生也能用起来的学习方法。',
  },
]

function fallbackImage(city) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160">
    <defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#274a6d"/><stop offset="1" stop-color="#142437"/>
    </linearGradient></defs>
    <rect width="160" height="160" fill="url(#g)"/>
    <text x="50%" y="55%" text-anchor="middle" font-size="26" fill="rgba(255,255,255,0.7)"
      font-family="sans-serif">${city}</text>
  </svg>`
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`
}

// —— 单个城市：大图铺屏 → 飞向地图上的位置
function FlyingHero({ project, position }) {
  const style = useMemo(() => {
    const W = window.innerWidth
    const H = window.innerHeight
    return {
      '--dx': `${position[0] - W / 2}px`,
      '--dy': `${position[1] - H / 2}px`,
      '--end': 200 / (W * 0.78),
    }
  }, [position])

  return (
    <div className="intro-layer">
      <img
        className="intro-hero"
        src={project.image.replace('/320/320', '/1200/900')}
        alt={project.title}
        style={style}
        onError={(e) => {
          if (e.currentTarget.dataset.fb) return
          e.currentTarget.dataset.fb = '1'
          e.currentTarget.src = fallbackImage(project.city)
        }}
      />
    </div>
  )
}

function MapScene({ revealCount, onLayout }) {
  const containerRef = useRef(null)
  const chartRef = useRef(null)
  const navigate = useNavigate()

  const [mapReady, setMapReady] = useState(false)
  const [dotPx, setDotPx] = useState([])
  const [size, setSize] = useState({ w: 0, h: 0 })

  const revealed = Math.min(revealCount, projects.length)

  // 1. 加载地图数据
  useEffect(() => {
    let cancelled = false
    fetch('/china.json')
      .then((res) => res.json())
      .then((geoJson) => {
        if (cancelled) return
        echarts.registerMap('china', geoJson)
        setMapReady(true)
      })
      .catch((err) => console.error('地图数据加载失败', err))
    return () => { cancelled = true }
  }, [])

  // 2. 监听容器尺寸
  useEffect(() => {
    const el = containerRef.current
    if (!el) return
    const sync = () => {
      setSize({ w: el.clientWidth, h: el.clientHeight })
      chartRef.current?.resize()
    }
    sync()
    const ro = new ResizeObserver(sync)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  // 3. 初始化地图
  useEffect(() => {
    if (!mapReady || !containerRef.current) return
    const chart = echarts.init(containerRef.current)
    chartRef.current = chart

    chart.setOption({
      geo: {
        map: 'china',
        roam: false,
        left: '16%',
        right: '16%',
        top: 70,
        bottom: 50,
        itemStyle: {
          areaColor: 'rgba(96, 150, 220, 0.07)',
          borderColor: 'rgba(120, 180, 255, 0.32)',
          borderWidth: 1,
        },
        emphasis: { disabled: true },
        silent: true,
      },
      series: [
        {
          type: 'effectScatter',
          coordinateSystem: 'geo',
          data: [],
          symbolSize: 9,
          rippleEffect: { brushType: 'stroke', scale: 5, period: 3.6 },
          itemStyle: {
            color: '#ffb547',
            shadowBlur: 14,
            shadowColor: 'rgba(255, 181, 71, 0.9)',
          },
          animationDurationUpdate: 400,
        },
      ],
    })

    return () => {
      chart.dispose()
      chartRef.current = null
    }
  }, [mapReady])

  // 4. 把所有城市的地图像素坐标交给父组件
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !mapReady || !size.w) return
    const all = projects.map((p) => chart.convertToPixel({ geoIndex: 0 }, [p.lng, p.lat]))
    if (all.some((pt) => !pt)) return
    onLayout(all)
  }, [mapReady, size, onLayout])

  // 5. 光点数据 + 全部城市的像素坐标
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !mapReady) return
    chart.setOption({
      series: [{
        data: projects
          .slice(0, revealed)
          .map((p) => ({ name: p.city, value: [p.lng, p.lat] })),
      }],
    })
    setDotPx(projects.map((p) => chart.convertToPixel({ geoIndex: 0 }, [p.lng, p.lat])))
  }, [mapReady, revealed, size])

  // 6. 卡片布局（一次算全部位置，避免后面卡片出现时推动前面的）
  const cards = useMemo(() => {
    if (!size.w || !size.h || dotPx.length !== projects.length) return []

    const all = projects.map((p, i) => {
      const [dotX, dotY] = dotPx[i]
      return {
        ...p,
        dotX,
        dotY,
        side: dotX < size.w / 2 ? 'left' : 'right',
        cardY: dotY - CARD_H / 2,
      }
    })

    const groups = {
      left: all.filter((x) => x.side === 'left').sort((a, b) => a.dotY - b.dotY),
      right: all.filter((x) => x.side === 'right').sort((a, b) => a.dotY - b.dotY),
    }
    const minY = { left: 230, right: 120 }

    Object.entries(groups).forEach(([key, group]) => {
      let cursor = minY[key]
      group.forEach((it) => {
        it.cardY = Math.max(it.cardY, cursor)
        cursor = it.cardY + CARD_H + CARD_GAP
      })
      const last = group[group.length - 1]
      if (last) {
        const overflow = last.cardY + CARD_H - (size.h - 60)
        if (overflow > 0) {
          group.forEach((it) => {
            it.cardY = Math.max(minY[key], it.cardY - overflow)
          })
        }
      }
    })

    return all.map((it, i) => ({
      ...it,
      visible: i < revealed,
      cardX: it.side === 'left' ? EDGE : size.w - EDGE - CARD_W,
      anchorX: it.side === 'left' ? EDGE + CARD_W : size.w - EDGE,
      anchorY: it.cardY + CARD_H / 2,
    }))
  }, [dotPx, size, revealed])

  return (
    <div className="map-scene">
      <div ref={containerRef} className="map-canvas" />

      <svg className="leader-layer" width={size.w} height={size.h}>
        {cards.filter((c) => c.visible).map((c) => (
          <line
            key={c.slug}
            x1={c.dotX}
            y1={c.dotY}
            x2={c.anchorX}
            y2={c.anchorY}
            className="leader-line"
            pathLength="1"
          />
        ))}
      </svg>

      {cards.filter((c) => c.visible).map((c) => (
        <div
          key={c.slug}
          className="map-card"
          style={{ left: c.cardX, top: c.cardY, width: CARD_W }}
          onClick={() => navigate(`/project/${c.slug}`)}
        >
          <img
            className="map-card__img"
            src={c.image}
            alt={c.city}
            onError={(e) => {
              if (e.currentTarget.dataset.fb) return
              e.currentTarget.dataset.fb = '1'
              e.currentTarget.src = fallbackImage(c.city)
            }}
          />
          <div className="map-card__body">
            <div className="map-card__theme">
              {c.city} · {c.theme}
            </div>
            <div className="map-card__title">{c.title}</div>
            <div className="map-card__desc">{c.summary}</div>
          </div>
        </div>
      ))}
    </div>
  )
}

// —— 第 2 屏：时间轴
function TimelineSection() {
  const navigate = useNavigate()

  const sorted = useMemo(
    () => [...projects].sort((a, b) => a.year - b.year || a.city.localeCompare(b.city)),
    []
  )

  return (
    <section className="scene">
      <div className="scene-inner">
        <div className="scene-head">
          <div className="hero-eyebrow">Timeline</div>
          <h2 className="scene-title">活动时间轴</h2>
          <p className="scene-sub">
            从好奇出发，{projects.length} 个学习项目，一条不断生长的探究脉络。
          </p>
        </div>

        <div className="timeline">
          {sorted.map((p, i) => (
            <div key={p.slug} className={`tl-row ${i % 2 === 0 ? 'left' : 'right'}`}>
              <div className="tl-card" onClick={() => navigate(`/project/${p.slug}`)}>
                <img
                  className="tl-thumb"
                  src={p.image.replace('/320/320', '/400/400')}
                  alt={p.title}
                  onError={(e) => {
                    if (e.currentTarget.dataset.fb) return
                    e.currentTarget.dataset.fb = '1'
                    e.currentTarget.src = fallbackImage(p.city)
                  }}
                />
                <div className="tl-body">
                  <div className="tl-meta">
                    {p.cohort} · {p.city} · {p.theme}
                  </div>
                  <div className="tl-title">{p.title}</div>
                  <div className="tl-desc">{p.summary}</div>
                </div>
              </div>
              <span className="tl-node" />
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// —— 第 3 屏：按主题分类
function ThemeSection() {
  const navigate = useNavigate()

  const groups = useMemo(() => {
    const map = new Map()
    projects.forEach((p) => {
      if (!map.has(p.theme)) map.set(p.theme, [])
      map.get(p.theme).push(p)
    })
    return [...map.entries()].sort((a, b) => b[1].length - a[1].length)
  }, [])

  return (
    <section className="scene">
      <div className="scene-inner">
        <div className="scene-head">
          <div className="hero-eyebrow">Themes</div>
          <h2 className="scene-title">按主题分类</h2>
          <p className="scene-sub">
            同一片土地上的不同问题意识，{groups.length} 个主题，覆盖全部 {projects.length} 个项目。
          </p>
        </div>

        <div className="theme-grid">
          {groups.map(([theme, items]) => (
            <div className="theme-block" key={theme}>
              <div className="theme-head">
                <div className="theme-name">{theme}</div>
                <div className="theme-count">{items.length} 个项目</div>
              </div>
              <p className="theme-desc">{THEME_DESC[theme] || '相关田野与调研'}</p>

              <div className="theme-items">
                {items.map((p) => (
                  <div
                    className="theme-item"
                    key={p.slug}
                    onClick={() => navigate(`/project/${p.slug}`)}
                  >
                    <img
                      src={p.image}
                      alt={p.title}
                      onError={(e) => {
                        if (e.currentTarget.dataset.fb) return
                        e.currentTarget.dataset.fb = '1'
                        e.currentTarget.src = fallbackImage(p.city)
                      }}
                    />
                    <div className="theme-item-body">
                      <div className="theme-item-title">{p.title}</div>
                      <div className="theme-item-meta">
                        {p.city} · {p.cohort}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}

// —— 第 4 屏：价值与意义
function ValueSection() {
  const stats = useMemo(
    () => [
      { n: projects.length, l: '个项目' },
      { n: new Set(projects.map((p) => p.city)).size, l: '座城市' },
      { n: new Set(projects.map((p) => p.theme)).size, l: '个主题' },
      {
        n: Object.values(projectDetails).reduce((sum, d) => {
          return sum
            + (d.origin?.audio ? 1 : 0)
            + (d.journey?.length || 0)
            + (d.outcome?.audio ? 1 : 0)
            + (d.gains?.audio ? 1 : 0)
        }, 0),
        l: '段配音',
      },
    ],
    []
  )

  return (
    <section className="scene">
      <div className="scene-inner">
        <div className="scene-head">
          <div className="hero-eyebrow">Impact</div>
          <h2 className="scene-title">项目的价值与意义</h2>
          <p className="scene-sub">
            教育、社会与方法三个层面，孩子们的学习项目留下的不只是作品。
          </p>
        </div>

        <div className="value-stats">
          {stats.map((s) => (
            <div className="value-stat" key={s.l}>
              <b>{s.n}</b>
              <span>{s.l}</span>
            </div>
          ))}
        </div>

        <div className="value-grid">
          {VALUE_ITEMS.map((v) => (
            <div className="value-card" key={v.title}>
              <div className="value-label">{v.label}</div>
              <div className="value-title">{v.title}</div>
              <p className="value-lead">{v.lead}</p>
              <p className="value-desc">{v.desc}</p>
            </div>
          ))}
        </div>

        <div className="value-links">
          {projects.map((p) => (
            <Link key={p.slug} className="value-link" to={`/project/${p.slug}`}>
              {p.city} · {p.title}
            </Link>
          ))}
        </div>

        <p className="value-note">
          项目过程依据照片与公开资料整理；开场插画与配音由 AI 生成，来源见各项目详情页。
        </p>
      </div>
    </section>
  )
}

function HomePage() {
  const [layout, setLayout] = useState([])
  const layoutReady = layout.length === projects.length
  const [step, setStep] = useState(0)
  const introDone = step >= projects.length

  // 每个城市播完一轮，进入下一个
  useEffect(() => {
    if (!layoutReady || step >= projects.length) return
    const timer = setTimeout(() => setStep((s) => s + 1), CYCLE_MS)
    return () => clearTimeout(timer)
  }, [layoutReady, step])

  return (
      <div className="page-stack">

      {/* 第 1 屏：地图 */}
      <section className="map-hero">
        <MapScene revealCount={step} onLayout={setLayout} />

        {!introDone && layoutReady && (
          <FlyingHero
            key={step}
            project={projects[step]}
            position={layout[step]}
          />
        )}

        <div className="hero-title">
          <div className="hero-eyebrow">Dream Journey</div>
          <h1 className="hero-h1">沿着光点，读一场场田野</h1>
          <p className="hero-sub">学生探究项目 · 点击卡片进入详情</p>
        </div>

        <div className="hero-legend">
          <i /> 项目地点
        </div>
      </section>

      {/* 第 2 / 3 / 4 屏 */}
      <TimelineSection />
      <ThemeSection />
      <ValueSection />
    </div>
  )
}

// —— 配音播放按钮（同时只播一段）
let currentAudio = null

function AudioButton({ src }) {
  const [playing, setPlaying] = useState(false)
  const ref = useRef(null)

  useEffect(() => () => ref.current?.pause(), [])

  const toggle = () => {
    const a = ref.current
    if (!a) return
    if (playing) {
      a.pause()
      setPlaying(false)
      if (currentAudio === a) currentAudio = null
      return
    }
    if (currentAudio && currentAudio !== a) currentAudio.pause()
    currentAudio = a
    a.play()
    setPlaying(true)
    a.onended = () => setPlaying(false)
  }

  return (
    <span
      className={`audio-btn ${playing ? 'is-playing' : ''}`}
      role="button"
      tabIndex={0}
      onClick={toggle}
      onKeyDown={(e) => { if (e.key === 'Enter') toggle() }}
    >
      <audio ref={ref} src={src} preload="none" />
      <span className="audio-icon">{playing ? '❚❚' : '▶'}</span>
      <span className="audio-label">{playing ? '暂停' : 'AI 配音'}</span>
    </span>
  )
}

function MediaFigure({ src, caption }) {
  return (
    <figure className="d-media">
      <img src={src} alt={caption || ''} />
      {caption && <figcaption>{caption}</figcaption>}
    </figure>
  )
}

function ProjectDetail() {
  const { slug } = useParams()
  const index = projects.findIndex((p) => p.slug === slug)
  const project = projects[index]
  const detail = projectDetails[slug]

  if (!project || !detail) {
    return (
      <div className="detail">
        <div className="detail-body">
          <p>没有找到这个项目。</p>
          <Link className="back-link" to="/">← 返回地图</Link>
        </div>
      </div>
    )
  }

  const prev = projects[(index - 1 + projects.length) % projects.length]
  const next = projects[(index + 1) % projects.length]
  const title = detail.title || project.title

  return (
    <div className="detail">
      <header
        className="detail-hero"
        style={{ backgroundImage: `url(${project.image})` }}
      >
        <Link className="detail-back" to="/">← 返回地图</Link>

        <div className="detail-hero-inner">
          <div className="detail-eyebrow">
            {project.cohort} · {project.theme} · {project.city}
          </div>
          <h1 className="detail-title">{title}</h1>
          <p className="detail-summary">{project.summary}</p>

          <div className="detail-chips">
            <span className="detail-chip">{detail.location}</span>
            {detail.chips.map((c) => (
              <span className="detail-chip" key={c}>{c}</span>
            ))}
            {detail.demoChip && (
              <span className="detail-chip detail-chip--demo">{detail.demoChip}</span>
            )}
          </div>
        </div>
      </header>

      <div className="detail-body">
        {/* 项目起因 */}
        {detail.origin && (
          <section className="d-block">
            <h2 className="d-h2">Why · 项目起因</h2>
            <div className="d-origin">
              <div className="d-origin-text">
                <p className="d-question">{detail.origin.text}</p>
                {detail.origin.audio && <AudioButton src={detail.origin.audio} />}
              </div>
              {detail.origin.image && (
                <MediaFigure src={detail.origin.image} caption={detail.origin.imageCaption} />
              )}
            </div>
          </section>
        )}

        {/* 研究问题 */}
        {detail.subQuestions && (
          <section className="d-block">
            <h2 className="d-h2">Questions · 我们想知道什么</h2>
            <ol className="d-questions">
              {detail.subQuestions.map((q) => (
                <li key={q}>{q}</li>
              ))}
            </ol>
          </section>
        )}

        {/* 研究方法 */}
        {detail.methods && (
          <section className="d-block">
            <h2 className="d-h2">Methods · 研究方法</h2>
            <div className="d-methods">
              {detail.methods.map((m) => (
                <span className="d-method" key={m}>{m}</span>
              ))}
            </div>
          </section>
        )}

        {/* 学习过程 */}
        {detail.journey && (
          <section className="d-block">
            <h2 className="d-h2">Process · 我们的学习过程</h2>
            <div className="d-journey">
              {detail.journey.map((j) => (
                <div className="d-step" key={j.time}>
                  <div className="d-step-time">{j.time}</div>
                  {j.title && <h3 className="d-step-title">{j.title}</h3>}
                  <p className="d-step-desc">{j.desc}</p>
                  {j.image && <MediaFigure src={j.image} caption={j.imageCaption} />}
                  {j.table && (
                    <div className="d-table-wrap">
                      <table className="d-table">
                        <thead>
                          <tr>
                            {j.table.columns.map((c) => (
                              <th key={c}>{c}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {j.table.rows.map((row) => (
                            <tr key={row[0]}>
                              {row.map((cell) => (
                                <td key={cell}>{cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      {j.table.note && <p className="d-table-note">{j.table.note}</p>}
                    </div>
                  )}
                  {(j.challenge || j.response) && (
                    <dl className="d-triple d-triple--pair">
                      <div>
                        <dt>困难</dt>
                        <dd>{j.challenge}</dd>
                      </div>
                      <div>
                        <dt>应对</dt>
                        <dd>{j.response}</dd>
                      </div>
                    </dl>
                  )}
                  {j.audio && <AudioButton src={j.audio} />}
                </div>
              ))}
            </div>
          </section>
        )}

        {/* 成果 */}
        {detail.outcome && (
          <section className="d-block">
            <h2 className="d-h2">Outcome · {detail.outcome.title}</h2>
            {detail.outcome.text && (
              <p className="d-step-desc">{detail.outcome.text}</p>
            )}
            {detail.outcome.points && (
              <div className="d-outcome">
                {detail.outcome.points.map((pt) => (
                  <div className="d-outcome-point" key={pt.label}>
                    <div className="d-outcome-label">{pt.label}</div>
                    <p>{pt.text}</p>
                  </div>
                ))}
              </div>
            )}
            {detail.outcome.image && (
              <MediaFigure src={detail.outcome.image} caption={detail.outcome.imageCaption} />
            )}
            {detail.outcome.audio && <AudioButton src={detail.outcome.audio} />}
          </section>
        )}

        {/* 学习收获 */}
        {detail.gains && (
          <section className="d-block">
            <h2 className="d-h2">Reflections · 学习收获</h2>
            <p className="d-step-desc">{detail.gains.text}</p>
            {detail.gains.audio && <AudioButton src={detail.gains.audio} />}
          </section>
        )}

        {/* 素材来源与说明 */}
        <section className="d-block">
          <h2 className="d-h2">Sources · 素材来源与说明</h2>
          {detail.sources && (
            <ul className="d-sources">
              {detail.sources.map((s) => (
                <li key={s.url}>
                  <a href={s.url} target="_blank" rel="noreferrer">{s.name}</a>
                  <span className="d-source-org">{s.org}</span>
                </li>
              ))}
            </ul>
          )}
          <ul className="d-notes">
            {detail.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </section>

        {/* 上下项目 */}
        <nav className="d-nav">
          <Link to={`/project/${prev.slug}`}>← {prev.city}</Link>
          <Link to="/">回到地图</Link>
          <Link to={`/project/${next.slug}`}>{next.city} →</Link>
        </nav>
      </div>
    </div>
  )
}


function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/project/:slug" element={<ProjectDetail />} />
      </Routes>
    </BrowserRouter>
  )
}
export default App
