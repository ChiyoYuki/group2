import { useEffect, useMemo, useRef, useState } from 'react'
import { BrowserRouter, Routes, Route, Link, useNavigate, useParams } from 'react-router-dom'
import * as echarts from 'echarts'

// —— 示例项目数据（对接后端后替换成接口返回）
const projects = [
  {
    slug: 'harbin-ice-architecture',
    city: '哈尔滨', lng: 126.5349, lat: 45.8038, year: 2026,
    title: '冰雪建筑的空间叙事',
    theme: '建筑', cohort: '2026 暑期',
    summary: '在零下二十度的中央大街，记录冰雪建筑如何塑造城市的冬日生活。',
    image: 'https://picsum.photos/seed/harbin/320/320',
  },
  {
    slug: 'beijing-hutong-memory',
    city: '北京', lng: 116.4074, lat: 39.9042, year: 2025,
    title: '胡同里的社区记忆',
    theme: '文化', cohort: '2025 暑期',
    summary: '走进南锣鼓巷的院落，用口述史拼出老北京的生活变迁。',
    image: 'https://picsum.photos/seed/beijing/320/320',
  },
  {
    slug: 'xian-heritage-site',
    city: '西安', lng: 108.9398, lat: 34.3416, year: 2025,
    title: '城墙内外的遗产现场',
    theme: '文化遗产', cohort: '2025 暑期',
    summary: '跟随考古队员的步伐，理解古都如何在保护与生活之间取得平衡。',
    image: 'https://picsum.photos/seed/xian/320/320',
  },
  {
    slug: 'chengdu-irrigation',
    city: '成都', lng: 104.0665, lat: 30.5723, year: 2026,
    title: '川西林盘的生态智慧',
    theme: '生态', cohort: '2026 暑期',
    summary: '在都江堰的田野间，调查传统灌溉如何延续两千年。',
    image: 'https://picsum.photos/seed/chengdu/320/320',
  },
  {
    slug: 'kunming-wetland',
    city: '昆明', lng: 102.8329, lat: 24.8801, year: 2026,
    title: '滇池湿地的候鸟守望',
    theme: '生态', cohort: '2026 暑期',
    summary: '与巡护员一起监测候鸟，记录一片湿地修复的真实进度。',
    image: 'https://picsum.photos/seed/kunming/320/320',
  },
  {
    slug: 'hangzhou-tea',
    city: '杭州', lng: 120.1551, lat: 30.2741, year: 2025,
    title: '龙井茶山的农事节奏',
    theme: '农业', cohort: '2025 暑期',
    summary: '跟着茶农过一个采茶季，理解一片叶子背后的社区协作。',
    image: 'https://picsum.photos/seed/hangzhou/320/320',
  },
  {
    slug: 'guangzhou-arcade',
    city: '广州', lng: 113.2644, lat: 23.1291, year: 2026,
    title: '骑楼下的公共生活',
    theme: '社区研究', cohort: '2026 暑期',
    summary: '测量骑楼廊道的温度与人群，讨论老街区如何更新。',
    image: 'https://picsum.photos/seed/guangzhou/320/320',
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
    lead: '把课堂搬到现场',
    desc: '学生在真实场地中完成提问、取证与表达，从被动接收知识转向主动生产知识。',
  },
  {
    label: 'Social',
    title: '社会影响',
    lead: '让研究回到社区',
    desc: '报告、口述档案与公共展陈回到当地，成为社区自我描述与协商的素材。',
  },
  {
    label: 'Method',
    title: '方法价值',
    lead: '可复用的田野方法',
    desc: '访谈提纲、观察记录与影像归档被整理成模板，供下一届学生直接使用。',
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
            从 2025 到 2026，{projects.length} 次田野，一条持续生长的研究脉络。
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
      { n: new Set(projects.map((p) => p.cohort)).size, l: '个届次' },
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
            教育、社会与方法三个层面，田野调研留下的不只是报告。
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
          示例数据：真实的影响结论需附证据出处（反馈记录、报告章节等）。
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
          <p className="hero-sub">往届学生实地调研项目 · 点击卡片进入详情</p>
        </div>

        <div className="hero-legend">
          <i /> 去过的城市（示例数据）
        </div>
      </section>

      {/* 第 2 / 3 / 4 屏 */}
      <TimelineSection />
      <ThemeSection />
      <ValueSection />
    </div>
  )
}

function ProjectDetail() {
  const { slug } = useParams()
  const project = projects.find((p) => p.slug === slug)

  return (
    <div className="detail-page">
      <div className="detail-inner">
        <Link className="back-link" to="/">← 返回地图</Link>

        {project ? (
          <>
            <img
              className="detail-cover"
              src={project.image.replace('/320/320', '/1000/600')}
              alt={project.title}
              onError={(e) => {
                if (e.currentTarget.dataset.fb) return
                e.currentTarget.dataset.fb = '1'
                e.currentTarget.src = fallbackImage(project.city)
              }}
            />
            <div className="detail-meta">
              {project.city} · {project.theme} · {project.cohort}
            </div>
            <h1 className="detail-title">{project.title}</h1>
            <p className="detail-summary">{project.summary}</p>
            <p className="detail-note">
              这是前端临时占位页。等后端详情接口就绪后，替换为真实的研究历程、成果与实践建议。
            </p>
          </>
        ) : (
          <p style={{ marginTop: 40 }}>没有找到这个项目。</p>
        )}
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
