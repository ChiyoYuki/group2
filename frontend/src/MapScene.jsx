import { useEffect, useRef, useState } from 'react'
import * as echarts from 'echarts/core'
import { EffectScatterChart } from 'echarts/charts'
import { GeoComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([EffectScatterChart, GeoComponent, TooltipComponent, CanvasRenderer])

export default function MapScene({ projects, onSelect }) {
  const element = useRef(null)
  const [error, setError] = useState('')
  useEffect(() => {
    const controller = new AbortController()
    let chart
    let observer
    fetch(`${import.meta.env.BASE_URL}china.json`, { signal: controller.signal })
      .then(response => {
        if (!response.ok) throw new Error('地图暂时不可用，仍可从项目列表浏览。')
        return response.json()
      }).then(geo => {
        if (controller.signal.aborted) return
        echarts.registerMap('journey-china', geo)
        // Only explicit location text is used. Province centers are schematic,
        // and missing locations never get fabricated coordinates.
        const regions = geo.features.map(feature => {
          const name = feature.properties.name
          const alias = name.replace(/壮族自治区|回族自治区|维吾尔自治区|自治区|特别行政区|省|市/g, '')
          const matches = projects.filter(project => project.location && !project.location.includes('示例') && project.location.includes(alias))
          return { name, value: [...(feature.properties.center || feature.properties.cp || []), matches.length], projects: matches }
        }).filter(region => region.projects.length && region.value.length === 3)
        chart = echarts.init(element.current)
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
        chart.setOption({
          animation: !reducedMotion,
          tooltip: { trigger: 'item', renderMode: 'richText', formatter: item => `${item.name}\n${item.data.projects.length} 个项目 · 点击查看\n省级示意位置` },
          geo: {
            map: 'journey-china', roam: false, silent: true,
            left: '4%', right: '4%', top: '7%', bottom: '6%',
            itemStyle: { areaColor: '#142a40', borderColor: '#41617b', borderWidth: 0.75, shadowColor: '#030c17', shadowBlur: 18 },
            emphasis: { disabled: true },
          },
          series: [{
            type: 'effectScatter', coordinateSystem: 'geo', data: regions,
            symbolSize: item => Math.min(17, 8 + item[2]),
            showEffectOn: reducedMotion ? 'emphasis' : 'render',
            rippleEffect: { scale: 3, brushType: 'stroke', period: 5 },
            itemStyle: { color: '#edb66f', shadowBlur: 15, shadowColor: '#e5a258' },
          }],
        })
        chart.on('click', event => { if (event.data?.projects) onSelect(event.data) })
        observer = new ResizeObserver(() => chart.resize())
        observer.observe(element.current)
      }).catch(error => { if (!controller.signal.aborted) setError(error.message) })
    return () => { controller.abort(); observer?.disconnect(); chart?.dispose() }
  }, [projects, onSelect])
  return <div className="map-scene" aria-label="项目分布地图，光点为明确地点的省级示意位置">
    <div className="map-canvas" ref={element} />
    {error && <p className="map-error" role="status">{error}</p>}
    <span className="map-coordinate" aria-hidden="true">CHINA · FIELD NOTES</span>
  </div>
}
