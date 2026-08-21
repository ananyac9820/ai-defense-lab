import { useEffect, useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';

/**
 * The Account Nebula.
 *
 * The graph level is the strongest evidence in the project, so it gets the treatment.
 * Accounts are nodes, transfers are edges, and the layout is a real force simulation
 * rather than a circle with points on it: mule structure has to emerge from the topology
 * or the view is decoration.
 *
 * Pass-through accounts, the ones where money in and money out are near-equal and nothing
 * ever rests, are drawn as filled cubes in the spot colour. Everything else is a hairline
 * outline. That is the whole visual grammar, and it matches the paper the page is
 * printed on.
 *
 * Layout runs once, deterministically, on a fixed number of iterations. A live physics
 * loop looks impressive and makes the same picture different every time it is shown,
 * which is the wrong trade for a figure someone is going to ask questions about.
 */

export interface NebulaNode {
  id: string;
  passthrough: number;
  degree: number;
  isMule: boolean;
}

export interface NebulaEdge {
  source: number;
  target: number;
}

interface Props {
  /** 0 to 1 across the section, from the scroll driver. */
  progress?: () => number;
  nodes: NebulaNode[];
  edges: NebulaEdge[];
  attacker: boolean;
  reduced: boolean;
}

const ITERATIONS = 220;
const REPULSION = 0.55;
const SPRING = 0.035;
const CENTRE_PULL = 0.012;

/** Deterministic pseudo-random, so the same graph always lays out the same way. */
function seeded(i: number): number {
  const x = Math.sin(i * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

function layout(nodes: NebulaNode[], edges: NebulaEdge[]): Float32Array {
  const n = nodes.length;
  const pos = new Float32Array(n * 3);
  for (let i = 0; i < n; i++) {
    // Seed pass-through accounts nearer the centre. The simulation still has to earn the
    // final structure, but starting them inside converges faster and more stably.
    const bias = nodes[i].passthrough > 0.8 ? 0.45 : 1.0;
    pos[i * 3] = (seeded(i) - 0.5) * 6 * bias;
    pos[i * 3 + 1] = (seeded(i + 991) - 0.5) * 6 * bias;
    pos[i * 3 + 2] = (seeded(i + 7717) - 0.5) * 6 * bias;
  }

  const disp = new Float32Array(n * 3);
  for (let step = 0; step < ITERATIONS; step++) {
    disp.fill(0);
    const cooling = 1 - step / ITERATIONS;

    // Repulsion. O(n^2), which is fine because the node set is capped well below a
    // thousand; anything larger would be unreadable on screen regardless.
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        let dx = pos[i * 3] - pos[j * 3];
        let dy = pos[i * 3 + 1] - pos[j * 3 + 1];
        let dz = pos[i * 3 + 2] - pos[j * 3 + 2];
        let d2 = dx * dx + dy * dy + dz * dz;
        if (d2 < 1e-4) {
          dx = seeded(i * j + step) - 0.5;
          dy = seeded(i * j + step + 13) - 0.5;
          dz = seeded(i * j + step + 29) - 0.5;
          d2 = 1e-4;
        }
        const force = REPULSION / d2;
        const d = Math.sqrt(d2);
        disp[i * 3] += (dx / d) * force;
        disp[i * 3 + 1] += (dy / d) * force;
        disp[i * 3 + 2] += (dz / d) * force;
        disp[j * 3] -= (dx / d) * force;
        disp[j * 3 + 1] -= (dy / d) * force;
        disp[j * 3 + 2] -= (dz / d) * force;
      }
    }

    for (const edge of edges) {
      const a = edge.source;
      const b = edge.target;
      const dx = pos[b * 3] - pos[a * 3];
      const dy = pos[b * 3 + 1] - pos[a * 3 + 1];
      const dz = pos[b * 3 + 2] - pos[a * 3 + 2];
      disp[a * 3] += dx * SPRING;
      disp[a * 3 + 1] += dy * SPRING;
      disp[a * 3 + 2] += dz * SPRING;
      disp[b * 3] -= dx * SPRING;
      disp[b * 3 + 1] -= dy * SPRING;
      disp[b * 3 + 2] -= dz * SPRING;
    }

    for (let i = 0; i < n; i++) {
      disp[i * 3] -= pos[i * 3] * CENTRE_PULL;
      disp[i * 3 + 1] -= pos[i * 3 + 1] * CENTRE_PULL;
      disp[i * 3 + 2] -= pos[i * 3 + 2] * CENTRE_PULL;

      const limit = 0.28 * cooling;
      for (let k = 0; k < 3; k++) {
        const v = Math.max(-limit, Math.min(limit, disp[i * 3 + k]));
        pos[i * 3 + k] += v;
      }
    }
  }
  return pos;
}

function Graph({ nodes, edges, attacker, reduced, progress }: Props) {
  const group = useRef<THREE.Group>(null);
  const flagged = useRef<THREE.InstancedMesh>(null);
  const ordinary = useRef<THREE.InstancedMesh>(null);
  const lines = useRef<THREE.LineSegments>(null);
  const { invalidate, camera } = useThree();

  const positions = useMemo(() => layout(nodes, edges), [nodes, edges]);
  // Explicit hex for the same reason as the helix: WebGL materials cannot read CSS vars.
  const spot = attacker ? '#c43d18' : '#0f5c4a';
  const ink = '#14140f';

  const hot = useMemo(
    () => nodes.map((n, i) => ({ n, i })).filter(({ n }) => n.passthrough > 0.85),
    [nodes]
  );
  const cool = useMemo(
    () => nodes.map((n, i) => ({ n, i })).filter(({ n }) => n.passthrough <= 0.85),
    [nodes]
  );

  const edgeGeometry = useMemo(() => {
    const array = new Float32Array(edges.length * 6);
    edges.forEach((edge, k) => {
      array[k * 6] = positions[edge.source * 3];
      array[k * 6 + 1] = positions[edge.source * 3 + 1];
      array[k * 6 + 2] = positions[edge.source * 3 + 2];
      array[k * 6 + 3] = positions[edge.target * 3];
      array[k * 6 + 4] = positions[edge.target * 3 + 1];
      array[k * 6 + 5] = positions[edge.target * 3 + 2];
    });
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(array, 3));
    return geometry;
  }, [edges, positions]);

  // Instanced, because a thousand separate meshes is a thousand draw calls and this has
  // to hold 60fps on a laptop that is also running a screen share.
  useEffect(() => {
    const matrix = new THREE.Matrix4();
    const place = (mesh: THREE.InstancedMesh | null, set: { n: NebulaNode; i: number }[]) => {
      if (!mesh) return;
      set.forEach(({ n, i }, k) => {
        const scale = 0.05 + Math.min(0.11, n.degree * 0.006);
        matrix.makeScale(scale, scale, scale);
        matrix.setPosition(positions[i * 3], positions[i * 3 + 1], positions[i * 3 + 2]);
        mesh.setMatrixAt(k, matrix);
      });
      mesh.count = set.length;
      mesh.instanceMatrix.needsUpdate = true;
    };
    place(flagged.current, hot);
    place(ordinary.current, cool);
    invalidate();
  }, [hot, cool, positions, invalidate]);

  useFrame((_, delta) => {
    if (reduced) {
      if (lines.current) lines.current.geometry.setDrawRange(0, Infinity);
      if (flagged.current) flagged.current.count = hot.length;
      return;
    }
    const p = progress ? progress() : 1;

    // Edges draw in sequence, then nodes settle, then the pass-through accounts fill
    // last - the order the eye should read them in.
    if (lines.current) {
      lines.current.geometry.setDrawRange(0, Math.ceil(edges.length * 2 * Math.min(1, p * 1.3)));
    }
    if (flagged.current) {
      const reveal = Math.max(0, p * 1.6 - 0.6);
      flagged.current.count = Math.min(hot.length, Math.ceil(hot.length * reveal));
    }

    if (group.current) {
      // Slow orbit, plus a camera that rises as the section scrolls, so the graph is
      // something the viewer moves through rather than a picture of a graph.
      group.current.rotation.y += delta * 0.05;
      camera.position.y = 3.4 - p * 2.2;
      camera.lookAt(0, 0, 0);
    }
    invalidate();
  });

  return (
    <group ref={group}>
      <lineSegments ref={lines}>
        <primitive object={edgeGeometry} attach="geometry" />
        <lineBasicMaterial attach="material" color={ink} opacity={0.22} transparent />
      </lineSegments>

      <instancedMesh ref={ordinary} args={[undefined, undefined, Math.max(cool.length, 1)]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial color={ink} opacity={0.4} transparent wireframe />
      </instancedMesh>

      <instancedMesh ref={flagged} args={[undefined, undefined, Math.max(hot.length, 1)]}>
        <boxGeometry args={[1, 1, 1]} />
        <meshBasicMaterial color={spot} />
      </instancedMesh>
    </group>
  );
}

export default function AccountNebula3D({ nodes, edges, attacker, reduced, progress }: Props) {
  if (!nodes.length) return null;
  const flagged = nodes.filter((n) => n.passthrough > 0.85).length;
  return (
    <div className="relative" style={{ height: 460 }}>
      <Canvas
        orthographic
        camera={{ position: [5, 3.4, 5], zoom: 74, near: 0.1, far: 200 }}
        frameloop={reduced ? 'demand' : 'always'}
        gl={{ antialias: true, alpha: true }}
        style={{ background: 'transparent' }}
      >
        <Graph nodes={nodes} edges={edges} attacker={attacker} reduced={reduced} progress={progress} />
      </Canvas>
      <div className="tag pointer-events-none absolute bottom-0 left-0">
        {nodes.length} accounts · {edges.length} transfers · {flagged} pass-through, filled
      </div>
    </div>
  );
}
