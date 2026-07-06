"use client"

import { useEffect, useRef } from "react"
import { useRouter } from "next/navigation"
import * as THREE from "three"
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js"
import { motion } from "framer-motion"
import { Bot, Shield } from "lucide-react"
import { Button } from "@/components/ui/button"

function HeroScene() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    if (!canvasRef.current) return
    const canvas = canvasRef.current
    const scene = new THREE.Scene()
    scene.background = new THREE.Color(0x09090b)

    const camera = new THREE.PerspectiveCamera(45, canvas.clientWidth / canvas.clientHeight, 0.1, 100)
    camera.position.set(8, 4, 10)
    camera.lookAt(0, 0, 0)

    const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true })
    renderer.setSize(canvas.clientWidth, canvas.clientHeight)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
    renderer.shadowMap.enabled = true
    renderer.shadowMap.type = THREE.PCFShadowMap
    renderer.toneMapping = THREE.ACESFilmicToneMapping
    renderer.toneMappingExposure = 1.2

    const controls = new OrbitControls(camera, canvas)
    controls.enableDamping = true
    controls.dampingFactor = 0.05
    controls.autoRotate = true
    controls.autoRotateSpeed = 0.8
    controls.maxPolarAngle = Math.PI / 2.4
    controls.minPolarAngle = Math.PI / 4
    controls.enableZoom = false
    controls.enablePan = false
    controls.target.set(0, 0, 0)

    const ambientLight = new THREE.AmbientLight(0x404060, 0.4)
    scene.add(ambientLight)
    const mainLight = new THREE.DirectionalLight(0x8b5cf6, 2)
    mainLight.position.set(5, 10, 5)
    mainLight.castShadow = true
    scene.add(mainLight)
    const fillLight = new THREE.DirectionalLight(0x6366f1, 1)
    fillLight.position.set(-5, 0, 5)
    scene.add(fillLight)
    const rimLight = new THREE.DirectionalLight(0xa78bfa, 0.8)
    rimLight.position.set(0, -3, -8)
    scene.add(rimLight)
    const pointLight = new THREE.PointLight(0x8b5cf6, 1, 15)
    pointLight.position.set(0, -2, 0)
    scene.add(pointLight)

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(20, 20),
      new THREE.MeshStandardMaterial({ color: 0x111113, roughness: 0.8, metalness: 0.2, transparent: true, opacity: 0.6 })
    )
    floor.rotation.x = -Math.PI / 2
    floor.position.y = -1.2
    floor.receiveShadow = true
    scene.add(floor)

    const gridHelper = new THREE.GridHelper(20, 40, 0x27272a, 0x1c1c20)
    gridHelper.position.y = -1.1
    scene.add(gridHelper)

    function createRack(x: number, z: number, height: number, color: number) {
      const group = new THREE.Group()
      const metalMat = new THREE.MeshStandardMaterial({ color, roughness: 0.3, metalness: 0.8 })
      for (let i = 0; i < height; i++) {
        const shelf = new THREE.Mesh(new THREE.BoxGeometry(1.8, 0.05, 0.8), metalMat)
        shelf.position.y = i * 0.7
        shelf.castShadow = true
        group.add(shelf)
        const boxMat = new THREE.MeshStandardMaterial({
          color: new THREE.Color(color).offsetHSL(0, 0, (i % 3) * 0.05),
          roughness: 0.4, metalness: 0.2,
          emissive: new THREE.Color(color), emissiveIntensity: 0.02,
        })
        const box = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.3, 0.5), boxMat)
        box.position.y = i * 0.7 + 0.2
        box.castShadow = true
        group.add(box)
      }
      const frameMat = new THREE.MeshStandardMaterial({ color: 0x27272a, roughness: 0.4, metalness: 0.6 })
      for (let i = 0; i < 4; i++) {
        const pillar = new THREE.Mesh(new THREE.BoxGeometry(0.04, height * 0.7 + 0.1, 0.04), frameMat)
        pillar.position.set(i < 2 ? -0.9 : 0.9, height * 0.35, i % 2 === 0 ? -0.4 : 0.4)
        group.add(pillar)
      }
      group.position.set(x, -1.2, z)
      return group
    }

    const rackPositions = [
      { x: -3, z: -2, h: 5, c: 0x6366f1 },
      { x: 0, z: -2, h: 6, c: 0x8b5cf6 },
      { x: 3, z: -2, h: 4, c: 0x6366f1 },
      { x: -2, z: 2, h: 5, c: 0x7c3aed },
      { x: 2, z: 2, h: 5, c: 0x6366f1 },
    ]
    rackPositions.forEach((r) => scene.add(createRack(r.x, r.z, r.h, r.c)))

    const glowRing = new THREE.Mesh(
      new THREE.RingGeometry(2.5, 3, 64),
      new THREE.MeshBasicMaterial({ color: 0x8b5cf6, transparent: true, opacity: 0.1, side: THREE.DoubleSide })
    )
    glowRing.rotation.x = -Math.PI / 2
    glowRing.position.y = -0.8
    scene.add(glowRing)

    const innerRing = new THREE.Mesh(
      new THREE.RingGeometry(1.5, 1.8, 48),
      new THREE.MeshBasicMaterial({ color: 0x6366f1, transparent: true, opacity: 0.15, side: THREE.DoubleSide })
    )
    innerRing.rotation.x = -Math.PI / 2
    innerRing.position.y = -0.6
    scene.add(innerRing)

    const particleCount = 500
    const particlesGeo = new THREE.BufferGeometry()
    const positions = new Float32Array(particleCount * 3)
    for (let i = 0; i < particleCount * 3; i++) positions[i] = (Math.random() - 0.5) * 20
    particlesGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3))
    const particles = new THREE.Points(
      particlesGeo,
      new THREE.PointsMaterial({ color: 0x8b5cf6, size: 0.02, transparent: true, opacity: 0.6, blending: THREE.AdditiveBlending })
    )
    particles.position.y = 2
    scene.add(particles)

    const mouse = { x: 0, y: 0 }
    function onMouseMove(e: MouseEvent) {
      mouse.x = (e.clientX / window.innerWidth) * 2 - 1
      mouse.y = -(e.clientY / window.innerHeight) * 2 + 1
    }
    window.addEventListener("mousemove", onMouseMove)

    function animate() {
      requestAnimationFrame(animate)
      controls.update()
      const time = Date.now() * 0.0005
      glowRing.rotation.z = time * 0.3
      innerRing.rotation.z = -time * 0.5
      particles.rotation.y = time * 0.02
      pointLight.position.x = Math.sin(time * 0.5) * 3
      pointLight.position.z = Math.cos(time * 0.5) * 3
      renderer.render(scene, camera)
    }
    animate()

    function handleResize() {
      if (!canvasRef.current) return
      const w = canvasRef.current.clientWidth
      const h = canvasRef.current.clientHeight
      camera.aspect = w / h
      camera.updateProjectionMatrix()
      renderer.setSize(w, h)
    }
    const resizeObserver = new ResizeObserver(handleResize)
    resizeObserver.observe(canvas.parentElement!)

    return () => {
      window.removeEventListener("mousemove", onMouseMove)
      resizeObserver.disconnect()
      renderer.dispose()
    }
  }, [])

  return <canvas ref={canvasRef} className="absolute inset-0 h-full w-full" />
}

export function WarehouseHero() {
  const router = useRouter()
  return (
    <section className="relative min-h-screen w-full overflow-hidden bg-hero">
      <div className="absolute inset-0 bg-gradient-to-b from-accent/5 via-transparent to-background" />
      <HeroScene />
      <div className="absolute inset-0 bg-gradient-to-t from-background via-transparent to-transparent" />

      <div className="relative z-10 flex min-h-screen flex-col items-center justify-center px-6 text-center">
        <motion.div initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: [0.25, 0.1, 0.25, 1] }}
          className="mb-4 flex items-center gap-2 rounded-full border border-accent/20 bg-accent/5 px-4 py-1.5 text-xs font-medium text-accent backdrop-blur-sm"
        >
          <Shield className="h-3 w-3" /> Enterprise Multi-Agent OS
        </motion.div>

        <motion.h1 initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.15, ease: [0.25, 0.1, 0.25, 1] }}
          className="max-w-4xl text-5xl font-bold leading-tight tracking-tight sm:text-6xl md:text-7xl lg:text-8xl"
        >
          Intelligence <span className="gradient-text">orchestrating</span><br />your warehouse
        </motion.h1>

        <motion.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.3, ease: [0.25, 0.1, 0.25, 1] }}
          className="mt-6 max-w-xl text-lg text-muted-foreground"
        >
          Deploy, monitor, and scale autonomous agents that manage inventory, optimize workflows, and predict demand in real time.
        </motion.p>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, delay: 0.45, ease: [0.25, 0.1, 0.25, 1] }}
          className="mt-8 flex items-center gap-4"
        >
          <Button size="xl" className="gap-2" onClick={() => router.push("/dashboard")}><Bot className="h-4 w-4" /> Launch Dashboard</Button>
        </motion.div>
      </div>
    </section>
  )
}
