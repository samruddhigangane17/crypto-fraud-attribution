import React, { useEffect, useRef, useState, useMemo } from 'react';
import { RotateCcw, Play, Pause, ZoomIn, ZoomOut, Compass } from 'lucide-react';

interface Sphere3DGraphProps {
  elements: any[];
  selectedNode: any;
  onSelectNode: (nodeData: any) => void;
  theme?: 'dark' | 'light';
}

interface Node3D {
  id: string;
  data: any;
  x: number;
  y: number;
  z: number;
  color: string;
  highlight: string;
  shadow: string;
  radius: number;
  isVictim: boolean;
  isVasp: boolean;
  isMixer: boolean;
}

interface Edge3D {
  sourceId: string;
  targetId: string;
  amount?: string;
  data: any;
}

export const Sphere3DGraph: React.FC<Sphere3DGraphProps> = ({
  elements,
  selectedNode,
  onSelectNode,
  theme = 'dark',
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [isAutoRotating, setIsAutoRotating] = useState(true);
  const [zoomLevel, setZoomLevel] = useState(1);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  // Camera angles
  const cameraRef = useRef({
    yaw: 0.3,
    pitch: 0.25,
    isDragging: false,
    lastX: 0,
    lastY: 0,
  });

  // Extract nodes and edges
  const { nodes3D, edges3D } = useMemo(() => {
    const rawNodes = elements.filter((el) => el.data && !el.data.source);
    const rawEdges = elements.filter((el) => el.data && el.data.source && el.data.target);

    const SPHERE_RADIUS = 180;
    const n = rawNodes.length;

    // Distribute nodes on 3D sphere
    const mappedNodes: Node3D[] = rawNodes.map((el, i) => {
      const d = el.data;
      const type = (d.type || '').toLowerCase();
      const isVictim = type === 'victim' || type === 'source';
      const isVasp = type === 'exchange' || type === 'vasp';
      const isMixer = type === 'mixer';

      let x = 0, y = 0, z = 0;

      if (isVictim) {
        // Victim wallet placed near top pole
        x = 0;
        y = -SPHERE_RADIUS * 0.85;
        z = SPHERE_RADIUS * 0.4;
      } else {
        // Fibonacci sphere distribution for other nodes
        const phi = Math.acos(1 - 2 * ((i + 0.5) / Math.max(1, n)));
        const theta = Math.PI * (1 + Math.sqrt(5)) * i;

        const jitterRadius = SPHERE_RADIUS * (isVasp ? 1.05 : 0.95);
        x = jitterRadius * Math.sin(phi) * Math.cos(theta);
        y = jitterRadius * Math.cos(phi);
        z = jitterRadius * Math.sin(phi) * Math.sin(theta);
      }

      // Shading colors
      let color = '#26736E';
      let highlight = '#89F792';
      let shadow = '#0D3533';
      let radius = 14;

      if (isVictim) {
        color = '#D95F63';
        highlight = '#FF9E9E';
        shadow = '#6E1A1E';
        radius = 18;
      } else if (isVasp) {
        color = '#79E282';
        highlight = '#C8FFCD';
        shadow = '#1B6B36';
        radius = 16;
      } else if (isMixer) {
        color = '#E6A94A';
        highlight = '#FFE082';
        shadow = '#7A4B08';
        radius = 15;
      } else if (type === 'bridge') {
        color = '#38BDF8';
        highlight = '#BAE6FD';
        shadow = '#0369A1';
        radius = 15;
      }

      return {
        id: d.id,
        data: d,
        x,
        y,
        z,
        color,
        highlight,
        shadow,
        radius,
        isVictim,
        isVasp,
        isMixer,
      };
    });

    const mappedEdges: Edge3D[] = rawEdges.map((el) => ({
      sourceId: el.data.source,
      targetId: el.data.target,
      amount: el.data.amount || el.data.label,
      data: el.data,
    }));

    return { nodes3D: mappedNodes, edges3D: mappedEdges };
  }, [elements]);

  // Animated flow particles along edges
  const particlesRef = useRef(
    edges3D.map(() => ({
      progress: Math.random(),
      speed: 0.005 + Math.random() * 0.005,
    }))
  );

  useEffect(() => {
    particlesRef.current = edges3D.map(() => ({
      progress: Math.random(),
      speed: 0.005 + Math.random() * 0.005,
    }));
  }, [edges3D]);

  // Main 3D Canvas Render Loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationId: number;
    let width = (canvas.width = canvas.parentElement?.clientWidth || 800);
    let height = (canvas.height = canvas.parentElement?.clientHeight || 600);

    const handleResize = () => {
      if (!canvas || !canvas.parentElement) return;
      width = canvas.width = canvas.parentElement.clientWidth;
      height = canvas.height = canvas.parentElement.clientHeight;
    };
    window.addEventListener('resize', handleResize);

    const render = () => {
      ctx.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2;

      // Auto-rotation if enabled
      if (isAutoRotating && !cameraRef.current.isDragging) {
        cameraRef.current.yaw += 0.004;
      }

      const yaw = cameraRef.current.yaw;
      const pitch = cameraRef.current.pitch;

      const cosY = Math.cos(yaw);
      const sinY = Math.sin(yaw);
      const cosP = Math.cos(pitch);
      const sinP = Math.sin(pitch);

      // Rotate and project nodes
      const projectedNodes = new Map<string, { px: number; py: number; pz: number; scale: number; node: Node3D }>();

      nodes3D.forEach((n) => {
        // Rotate Y (yaw)
        const x1 = n.x * cosY - n.z * sinY;
        const z1 = n.z * cosY + n.x * sinY;

        // Rotate X (pitch)
        const y2 = n.y * cosP - z1 * sinP;
        const z2 = z1 * cosP + n.y * sinP;

        // Apply Zoom & Perspective
        const fov = 650;
        const scale = (fov / (fov + z2)) * zoomLevel;

        const px = cx + x1 * scale;
        const py = cy + y2 * scale;

        projectedNodes.set(n.id, { px, py, pz: z2, scale, node: n });
      });

      // 1. Draw 3D Wireframe Globe Rings for depth
      ctx.save();
      const ringRadius = 180 * zoomLevel;
      ctx.strokeStyle = theme === 'dark' ? 'rgba(121, 226, 130, 0.08)' : 'rgba(15, 118, 110, 0.12)';
      ctx.lineWidth = 1;

      // Equator & meridian rings
      ctx.beginPath();
      ctx.ellipse(cx, cy, ringRadius, ringRadius * Math.abs(cosP), 0, 0, Math.PI * 2);
      ctx.stroke();

      ctx.beginPath();
      ctx.ellipse(cx, cy, ringRadius * Math.abs(cosY), ringRadius, 0, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // 2. Draw 3D Curved Edges & Energy Arcs
      edges3D.forEach((e, idx) => {
        const src = projectedNodes.get(e.sourceId);
        const tgt = projectedNodes.get(e.targetId);
        if (!src || !tgt) return;

        // Midpoint with outward 3D curvature
        const midX = (src.px + tgt.px) / 2;
        const midY = (src.py + tgt.py) / 2 - 35 * src.scale;

        // Depth fogging
        const avgZ = (src.pz + tgt.pz) / 2;
        const alpha = Math.max(0.12, Math.min(0.85, (avgZ + 250) / 500));

        // Draw curved arc
        ctx.beginPath();
        ctx.moveTo(src.px, src.py);
        ctx.quadraticCurveTo(midX, midY, tgt.px, tgt.py);

        ctx.strokeStyle = theme === 'dark'
          ? `rgba(121, 226, 130, ${alpha * 0.7})`
          : `rgba(15, 118, 110, ${alpha * 0.8})`;
        ctx.lineWidth = Math.max(1.2, 2 * src.scale);
        ctx.stroke();

        // Draw moving energy packet
        const pState = particlesRef.current[idx];
        if (pState) {
          pState.progress += pState.speed;
          if (pState.progress > 1) pState.progress = 0;

          const t = pState.progress;
          // Quadratic bezier interpolation: (1-t)^2 * P0 + 2*(1-t)*t * P1 + t^2 * P2
          const bx = (1 - t) * (1 - t) * src.px + 2 * (1 - t) * t * midX + t * t * tgt.px;
          const by = (1 - t) * (1 - t) * src.py + 2 * (1 - t) * t * midY + t * t * tgt.py;

          if (avgZ > -120) {
            ctx.save();
            ctx.fillStyle = '#79E282';
            ctx.shadowColor = '#79E282';
            ctx.shadowBlur = 10;
            ctx.beginPath();
            ctx.arc(bx, by, Math.max(2, 3.5 * src.scale), 0, Math.PI * 2);
            ctx.fill();
            ctx.restore();
          }
        }
      });

      // 3. Draw Nodes sorted by depth (Z-buffer painters algorithm)
      const sortedNodes = Array.from(projectedNodes.values()).sort((a, b) => a.pz - b.pz);

      sortedNodes.forEach(({ px, py, pz, scale, node }) => {
        const isHovered = hoveredNodeId === node.id;
        const isSelected = selectedNode && selectedNode.id === node.id;
        const r = node.radius * scale * (isHovered || isSelected ? 1.25 : 1);

        ctx.save();

        // Outer glow halo for selected or hovered node
        if (isSelected || isHovered || node.isVictim || node.isVasp) {
          ctx.beginPath();
          ctx.arc(px, py, r * 1.55, 0, Math.PI * 2);
          ctx.fillStyle = node.color;
          ctx.globalAlpha = isSelected ? 0.45 : isHovered ? 0.35 : 0.18;
          ctx.fill();
          ctx.globalAlpha = 1;
        }

        // Draw 3D Shaded Sphere (Radial Gradient)
        const lightOffsetX = px - r * 0.35;
        const lightOffsetY = py - r * 0.35;
        const sphereGrad = ctx.createRadialGradient(
          lightOffsetX,
          lightOffsetY,
          r * 0.08,
          px,
          py,
          r
        );
        sphereGrad.addColorStop(0, '#FFFFFF');
        sphereGrad.addColorStop(0.25, node.highlight);
        sphereGrad.addColorStop(0.65, node.color);
        sphereGrad.addColorStop(1, node.shadow);

        ctx.beginPath();
        ctx.arc(px, py, r, 0, Math.PI * 2);
        ctx.fillStyle = sphereGrad;
        ctx.shadowColor = node.color;
        ctx.shadowBlur = pz > 0 ? 12 : 3;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Rim border
        ctx.strokeStyle = isSelected ? '#FFFFFF' : node.highlight;
        ctx.lineWidth = isSelected ? 2.5 : 1.2;
        ctx.stroke();

        // Floating HUD Label Pill
        const labelText = node.data.label || node.data.reported_address || node.id;
        const shortLabel = labelText.length > 14 ? `${labelText.slice(0, 6)}...${labelText.slice(-4)}` : labelText;

        ctx.font = '600 10px Montserrat, sans-serif';
        const textWidth = ctx.measureText(shortLabel).width;
        const pillW = textWidth + 12;
        const pillH = 16;
        const pillX = px - pillW / 2;
        const pillY = py + r + 6;

        // Pill background
        ctx.fillStyle = theme === 'dark' ? 'rgba(17, 23, 26, 0.88)' : 'rgba(255, 255, 255, 0.92)';
        ctx.strokeStyle = theme === 'dark' ? 'rgba(121, 226, 130, 0.25)' : 'rgba(15, 118, 110, 0.35)';
        ctx.lineWidth = 1;

        ctx.beginPath();
        ctx.roundRect(pillX, pillY, pillW, pillH, 4);
        ctx.fill();
        ctx.stroke();

        // Label text
        ctx.fillStyle = theme === 'dark' ? '#E8EEEB' : '#0B1512';
        ctx.fillText(shortLabel, pillX + 6, pillY + 11.5);

        ctx.restore();
      });

      animationId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', handleResize);
    };
  }, [nodes3D, edges3D, isAutoRotating, zoomLevel, hoveredNodeId, selectedNode, theme]);

  // Mouse Interaction (Click & Drag Rotation, Hit-Testing)
  const handleMouseDown = (e: React.MouseEvent) => {
    cameraRef.current.isDragging = true;
    cameraRef.current.lastX = e.clientX;
    cameraRef.current.lastY = e.clientY;
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    if (cameraRef.current.isDragging) {
      const deltaX = e.clientX - cameraRef.current.lastX;
      const deltaY = e.clientY - cameraRef.current.lastY;
      cameraRef.current.lastX = e.clientX;
      cameraRef.current.lastY = e.clientY;

      cameraRef.current.yaw += deltaX * 0.007;
      cameraRef.current.pitch = Math.max(-1.2, Math.min(1.2, cameraRef.current.pitch + deltaY * 0.007));
    } else {
      // Hit testing for hover
      const cx = canvas.width / 2;
      const cy = canvas.height / 2;
      const yaw = cameraRef.current.yaw;
      const pitch = cameraRef.current.pitch;
      const cosY = Math.cos(yaw);
      const sinY = Math.sin(yaw);
      const cosP = Math.cos(pitch);
      const sinP = Math.sin(pitch);
      const fov = 650;

      let found: string | null = null;

      for (const n of nodes3D) {
        const x1 = n.x * cosY - n.z * sinY;
        const z1 = n.z * cosY + n.x * sinY;
        const y2 = n.y * cosP - z1 * sinP;
        const z2 = z1 * cosP + n.y * sinP;

        const scale = (fov / (fov + z2)) * zoomLevel;
        const px = cx + x1 * scale;
        const py = cy + y2 * scale;
        const r = (n.radius + 6) * scale;

        const dist = Math.hypot(mouseX - px, mouseY - py);
        if (dist <= r) {
          found = n.id;
          break;
        }
      }

      setHoveredNodeId(found);
      canvas.style.cursor = found ? 'pointer' : cameraRef.current.isDragging ? 'grabbing' : 'grab';
    }
  };

  const handleMouseUp = () => {
    if (cameraRef.current.isDragging) {
      cameraRef.current.isDragging = false;
    }
  };

  const handleClick = (e: React.MouseEvent) => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const cx = canvas.width / 2;
    const cy = canvas.height / 2;
    const yaw = cameraRef.current.yaw;
    const pitch = cameraRef.current.pitch;
    const cosY = Math.cos(yaw);
    const sinY = Math.sin(yaw);
    const cosP = Math.cos(pitch);
    const sinP = Math.sin(pitch);
    const fov = 650;

    for (const n of nodes3D) {
      const x1 = n.x * cosY - n.z * sinY;
      const z1 = n.z * cosY + n.x * sinY;
      const y2 = n.y * cosP - z1 * sinP;
      const z2 = z1 * cosP + n.y * sinP;

      const scale = (fov / (fov + z2)) * zoomLevel;
      const px = cx + x1 * scale;
      const py = cy + y2 * scale;
      const r = (n.radius + 8) * scale;

      const dist = Math.hypot(mouseX - px, mouseY - py);
      if (dist <= r) {
        onSelectNode(n.data);
        break;
      }
    }
  };

  const resetCamera = () => {
    cameraRef.current.yaw = 0.3;
    cameraRef.current.pitch = 0.25;
    setZoomLevel(1);
  };

  return (
    <div className="relative w-full h-full min-h-[500px] flex-1 overflow-hidden select-none bg-[var(--graph-bg)]">
      {/* 3D Canvas */}
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onClick={handleClick}
        className="w-full h-full block cursor-grab active:cursor-grabbing"
      />

      {/* Floating HUD Controls */}
      <div className="absolute top-4 right-4 z-20 flex items-center space-x-1.5 bg-[var(--bg-card)]/90 backdrop-blur-md p-1.5 rounded-xl border border-[var(--border-color)] shadow-xl">
        <button
          onClick={() => setIsAutoRotating(!isAutoRotating)}
          className={`p-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1 transition-colors ${
            isAutoRotating
              ? 'bg-[var(--accent-primary)]/15 text-[var(--accent-primary)]'
              : 'text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)]'
          }`}
          title={isAutoRotating ? 'Pause Rotation' : 'Auto Rotate 360°'}
        >
          {isAutoRotating ? <Pause className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
          <span className="text-[11px] hidden sm:inline">{isAutoRotating ? 'Spinning' : 'Paused'}</span>
        </button>

        <div className="h-4 w-px bg-[var(--border-color)]" />

        <button
          onClick={() => setZoomLevel((z) => Math.min(2.0, z * 1.2))}
          className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
          title="Zoom In"
        >
          <ZoomIn className="h-3.5 w-3.5" />
        </button>

        <button
          onClick={() => setZoomLevel((z) => Math.max(0.6, z * 0.8))}
          className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
          title="Zoom Out"
        >
          <ZoomOut className="h-3.5 w-3.5" />
        </button>

        <button
          onClick={resetCamera}
          className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-secondary)] transition-colors"
          title="Reset Camera"
        >
          <RotateCcw className="h-3.5 w-3.5" />
        </button>
      </div>

      {/* Floating 3D Navigation Guide Pill */}
      <div className="absolute bottom-4 left-4 z-10 flex items-center space-x-2 px-3 py-1.5 bg-[var(--bg-card)]/90 backdrop-blur-md rounded-xl border border-[var(--border-color)] text-[11px] text-[var(--text-muted)] font-mono shadow-md">
        <Compass className="h-3.5 w-3.5 text-[var(--accent-primary)] animate-spin" />
        <span>Click & drag to rotate 360° · Click any sphere to inspect telemetry</span>
      </div>
    </div>
  );
};

export default Sphere3DGraph;
