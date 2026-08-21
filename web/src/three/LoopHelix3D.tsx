import { useMemo, useRef } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import * as THREE from 'three';
import type { Generation, MissesFile } from '../lib/contracts';

/**
 * The Loop Helix.
 *
 * Generations descend as turns of a single helix. Radius carries the detection rate, so a
 * converging spiral IS the result rather than a decoration wrapped around it: each turn
 * that pulls inward is a round where more of the attack set was caught. Attack instances
 * that evaded the detector break off as fragments drifting outward from their turn.
 *
 * Drawn in the same language as the rest of the dossier. Hairline ink on paper, no
 * gradient, no glow, no material that could not be printed. The only colour is the spot,
 * which marks the selected generation and crosses over with the inversion.
 */

interface HelixProps {
  generations: Generation[];
  misses: MissesFile[];
  selected: number;
  attacker: boolean;
  reduced: boolean;
}

const TURN_SEGMENTS = 96;
const TURN_HEIGHT = 1.35;
const R_MIN = 0.55;
const R_MAX = 2.35;

/** Detection rate to radius. A fully caught generation collapses towards the axis. */
function radiusFor(rate: number): number {
  return R_MAX - (R_MAX - R_MIN) * Math.max(0, Math.min(1, rate));
}

function Helix({ generations, misses, selected, attacker, reduced }: HelixProps) {
  const group = useRef<THREE.Group>(null);
  const { invalidate } = useThree();

  const { curve, rings, fragments, ticks } = useMemo(() => {
    const points: THREE.Vector3[] = [];
    const rings: { y: number; radius: number; generation: number; rate: number }[] = [];
    const fragments: { position: THREE.Vector3; generation: number }[] = [];
    const ticks: { position: THREE.Vector3; label: string; generation: number }[] = [];

    generations.forEach((gen, index) => {
      const rate = gen.detection_rate ?? gen.metrics_seen.recall;
      const nextGen = generations[index + 1];
      const nextRate = nextGen ? (nextGen.detection_rate ?? nextGen.metrics_seen.recall) : rate;
      const y0 = -index * TURN_HEIGHT;

      for (let s = 0; s <= TURN_SEGMENTS; s++) {
        const t = s / TURN_SEGMENTS;
        // Interpolate towards the next generation's radius across the turn, so the helix
        // is continuous rather than a stack of separate circles.
        const r = radiusFor(rate + (nextRate - rate) * t);
        const angle = t * Math.PI * 2;
        points.push(new THREE.Vector3(Math.cos(angle) * r, y0 - t * TURN_HEIGHT, Math.sin(angle) * r));
      }

      rings.push({ y: y0, radius: radiusFor(rate), generation: gen.generation, rate });
      ticks.push({
        position: new THREE.Vector3(radiusFor(rate) + 0.22, y0, 0),
        label: `G${gen.generation}`,
        generation: gen.generation,
      });

      // Fragments: one per instance that evaded, capped so a bad generation does not
      // become a cloud. They sit outside their turn because that is where they escaped.
      const log = misses.find((m) => m.generation === gen.generation);
      const evaded = log?.misses.length ?? Math.round((1 - rate) * 20);
      const count = Math.min(evaded, 26);
      for (let k = 0; k < count; k++) {
        const angle = (k / Math.max(count, 1)) * Math.PI * 2 + index;
        const r = radiusFor(rate) + 0.35 + (k % 4) * 0.16;
        fragments.push({
          position: new THREE.Vector3(
            Math.cos(angle) * r,
            y0 - (k % 7) * (TURN_HEIGHT / 7),
            Math.sin(angle) * r
          ),
          generation: gen.generation,
        });
      }
    });

    return {
      curve: new THREE.BufferGeometry().setFromPoints(points),
      rings,
      fragments,
      ticks,
    };
  }, [generations, misses]);

  useFrame((_, delta) => {
    if (reduced || !group.current) return;
    group.current.rotation.y += delta * 0.08;
    invalidate();
  });

  // three.js parses colours itself and cannot read a CSS custom property, so the band's
  // ink and spot arrive as explicit hex rather than through the token system the rest of
  // the page uses.
  const spot = attacker ? '#c43d18' : '#0f5c4a';
  const ink = '#14140f';

  return (
    <group ref={group} position={[0, (generations.length - 1) * TURN_HEIGHT * 0.5, 0]}>
      {/* the axis the spiral converges towards */}
      <line>
        <bufferGeometry
          attach="geometry"
          {...new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0.4, 0),
            new THREE.Vector3(0, -generations.length * TURN_HEIGHT - 0.2, 0),
          ])}
        />
        <lineBasicMaterial attach="material" color={ink} opacity={0.28} transparent />
      </line>

      {/* the helix itself */}
      <line>
        <primitive object={curve} attach="geometry" />
        <lineBasicMaterial attach="material" color={ink} opacity={0.85} transparent />
      </line>

      {/* one reference circle per generation, in the plane of that turn */}
      {rings.map((ring) => {
        const isSelected = ring.generation === selected;
        const pts: THREE.Vector3[] = [];
        for (let s = 0; s <= 72; s++) {
          const a = (s / 72) * Math.PI * 2;
          pts.push(new THREE.Vector3(Math.cos(a) * ring.radius, ring.y, Math.sin(a) * ring.radius));
        }
        return (
          <line key={`ring-${ring.generation}`}>
            <primitive object={new THREE.BufferGeometry().setFromPoints(pts)} attach="geometry" />
            <lineBasicMaterial
              attach="material"
              color={isSelected ? spot : ink}
              opacity={isSelected ? 0.95 : 0.16}
              transparent
            />
          </line>
        );
      })}

      {/* evaded instances */}
      {fragments.map((fragment, i) => (
        <mesh key={`frag-${i}`} position={fragment.position}>
          <boxGeometry args={[0.055, 0.055, 0.055]} />
          <meshBasicMaterial
            color={fragment.generation === selected ? spot : ink}
            opacity={fragment.generation === selected ? 0.9 : 0.3}
            transparent
          />
        </mesh>
      ))}

      {/* generation markers */}
      {ticks.map((tick) => (
        <mesh key={`tick-${tick.generation}`} position={tick.position}>
          <boxGeometry args={[0.09, 0.09, 0.09]} />
          <meshBasicMaterial
            color={tick.generation === selected ? spot : ink}
            opacity={tick.generation === selected ? 1 : 0.45}
            transparent
          />
        </mesh>
      ))}
    </group>
  );
}

export default function LoopHelix3D({
  generations,
  misses,
  selected,
  attacker,
  reduced,
}: HelixProps) {
  if (!generations.length) return null;
  return (
    <div className="relative" style={{ height: 460 }}>
      <Canvas
        orthographic
        camera={{ position: [4.2, 1.6, 4.2], zoom: 96, near: 0.1, far: 100 }}
        frameloop={reduced ? 'demand' : 'always'}
        gl={{ antialias: true, alpha: true }}
        style={{ background: 'transparent' }}
      >
        <Helix
          generations={generations}
          misses={misses}
          selected={selected}
          attacker={attacker}
          reduced={reduced}
        />
      </Canvas>
      <div className="tag pointer-events-none absolute bottom-0 left-0">
        radius = detection rate · each turn is one generation · fragments evaded
      </div>
    </div>
  );
}
