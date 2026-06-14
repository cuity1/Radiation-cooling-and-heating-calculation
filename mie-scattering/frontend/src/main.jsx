import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import Plot from 'react-plotly.js';
import * as THREE from 'three';
import {
  Box,
  Cuboid,
  Cylinder,
  Download,
  Languages,
  Layers,
  Circle,
  Play,
  RefreshCw,
  RotateCcw,
  ScanLine,
  SlidersHorizontal,
} from 'lucide-react';
import './styles.css';

const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:9000';
const ACTIVE_SOLVERS = ['auto', 'mie', 'tmatrix', 'rcwa', 'grcwa', 'smart_proxy'];
const SCAN_DEFAULTS = {
  auto: { wavelength_points: 160, diameter_points: 80 },
  mie: { wavelength_points: 160, diameter_points: 80 },
  smart_proxy: { wavelength_points: 160, diameter_points: 80 },
  tmatrix: { wavelength_points: 100, diameter_points: 50 },
  rcwa: { wavelength_points: 12, diameter_points: 8 },
  grcwa: { wavelength_points: 12, diameter_points: 8 },
};
const RCWA_MAX_SCAN_POINTS = 96;

const materialPresets = ['TiO2', 'SiO2', 'Au', 'Ag', 'Al', 'glass', 'polystyrene', 'water', 'custom'];

const presetDefaults = {
  TiO2: { name: 'TiO2', n_real: 2.4, n_imag: 0 },
  SiO2: { name: 'SiO2', n_real: 1.46, n_imag: 0 },
  Au: { name: 'Au', n_real: 0.18, n_imag: 3.45 },
  Ag: { name: 'Ag', n_real: 0.14, n_imag: 3.98 },
  Al: { name: 'Al', n_real: 1.44, n_imag: 7.38 },
  glass: { name: 'glass', n_real: 1.52, n_imag: 0 },
  polystyrene: { name: 'polystyrene', n_real: 1.59, n_imag: 0 },
  water: { name: 'water', n_real: 1.33, n_imag: 0 },
  custom: { name: 'custom material', n_real: 1.8, n_imag: 0 },
};

const defaultConfig = {
  name: 'Nanoparticle scattering study',
  geometry: {
    type: 'sphere',
    size: {
      diameter: 0.8,
      height: 0.45,
      width: 0.8,
      depth: 0.8,
      inner_diameter: 0.45,
      shell_thickness: 0.175,
    },
  },
  material: {
    preset: 'TiO2',
    name: 'TiO2',
    n_real: 2.4,
    n_imag: 0,
    medium_n_real: 1,
    medium_n_imag: 0,
    shell_core_n_real: 1.45,
    shell_core_n_imag: 0,
  },
  substrate: {
    type: 'none',
    thickness: 0.5,
    metal_index_real: 0.18,
    metal_index_imag: 3.45,
  },
  array: {
    enabled: false,
    period_x: 1.2,
    period_y: 1.2,
    count_x: 1,
    count_y: 1,
  },
  scan: {
    wavelength_min: 0.3,
    wavelength_max: 2.5,
    wavelength_points: SCAN_DEFAULTS.auto.wavelength_points,
    diameter_min: 0.3,
    diameter_max: 2.5,
    diameter_points: SCAN_DEFAULTS.auto.diameter_points,
    spectrum_diameter: 0.9,
  },
  simulation: {
    solver: 'auto',
    resolution: 24,
    pml_thickness: 0.6,
    runtime: 180,
    cell_padding: 1.0,
    random_seed: 7,
  },
};

const translations = {
  en: {
    appTitle: 'Scattering study',
    fdtdSetup: 'Computation setup',
    unitShape: 'Particle geometry',
    materialGroup: 'Material',
    particleMaterial: 'Particle material',
    materialName: 'Material name',
    nReal: 'n real',
    nImag: 'n imag',
    mediumNReal: 'Medium n',
    mediumNImag: 'Medium k',
    shellCoreNReal: 'Core n',
    shellCoreNImag: 'Core k',
    diameter: 'Diameter (um)',
    height: 'Height (um)',
    width: 'Width (um)',
    depth: 'Depth (um)',
    innerDiameter: 'Inner dia. (um)',
    shellThickness: 'Shell (um)',
    substrate: 'Substrate',
    substrateThickness: 'Sub. thickness',
    solver: 'Solver',
    enableArray: 'Enable periodic array',
    periodX: 'Period X',
    periodY: 'Period Y',
    countX: 'Count X',
    countY: 'Count Y',
    scanRange: 'Scan range',
    wavelengthMin: 'WL min',
    wavelengthMax: 'WL max',
    wavelengthPoints: 'WL points',
    diameterPoints: 'D points',
    diameterMin: 'D min',
    diameterMax: 'D max',
    spectrumDiameter: 'Spectrum D',
    reset: 'Reset',
    resetView: 'Reset view. Right/middle drag or Shift+drag to pan.',
    runningAction: 'Running',
    runScan: 'Run scan',
    modelCell: '3D model',
    particle: 'particle',
    array: 'array',
    single: 'single',
    results: 'Results',
    noJob: 'No job yet',
    refreshJobs: 'Refresh jobs',
    globalPeakWl: 'peak wavelength',
    globalPeakD: 'peak diameter',
    crossSection: 'Csca peak',
    emptyResults: 'Run a scan to generate heatmap, spectrum, efficiency components, peak map, near-field data, and downloads.',
    wavelengthAxis: 'Wavelength (um)',
    diameterAxis: 'Particle diameter (um)',
    qscaAxis: 'Qsca',
    efficiencyAxis: 'Efficiency',
    peakWavelengthAxis: 'Peak wavelength (um)',
    nearFieldAlt: 'Near-field plot',
    history: 'History',
    jobs: 'Jobs',
    backendUnreachable: 'Backend is not reachable.',
    loadJobError: 'Could not load job.',
    csvParseError: 'Could not parse result CSV files.',
    autoAdjustedSolver: 'Scan grid was adjusted to fit the selected solver limits.',
    language: 'Language',
    zh: '中文',
    en: 'EN',
  },
  zh: {
    appTitle: '散射计算',
    fdtdSetup: '计算设置',
    unitShape: '颗粒几何',
    materialGroup: '材料',
    particleMaterial: '颗粒材料',
    materialName: '材料名称',
    nReal: '折射率 n',
    nImag: '消光系数 k',
    mediumNReal: '介质 n',
    mediumNImag: '介质 k',
    shellCoreNReal: '核层 n',
    shellCoreNImag: '核层 k',
    diameter: '直径 (um)',
    height: '高度 (um)',
    width: '宽度 (um)',
    depth: '深度 (um)',
    innerDiameter: '内径 (um)',
    shellThickness: '壳厚 (um)',
    substrate: '基底',
    substrateThickness: '基底厚度',
    solver: '求解器',
    enableArray: '启用周期阵列',
    periodX: 'X 周期',
    periodY: 'Y 周期',
    countX: 'X 数量',
    countY: 'Y 数量',
    scanRange: '扫描范围',
    wavelengthMin: '波长最小值',
    wavelengthMax: '波长最大值',
    wavelengthPoints: '波长点数',
    diameterPoints: '直径点数',
    diameterMin: '直径最小值',
    diameterMax: '直径最大值',
    spectrumDiameter: '光谱直径',
    reset: '重置',
    resetView: '重置视角。右键/中键拖拽或 Shift+拖拽可平移。',
    runningAction: '计算中',
    runScan: '开始扫描',
    modelCell: '三维模型',
    particle: '颗粒',
    array: '阵列',
    single: '单颗粒',
    results: '计算结果',
    noJob: '暂无任务',
    refreshJobs: '刷新任务',
    globalPeakWl: '峰值波长',
    globalPeakD: '峰值直径',
    crossSection: '峰值散射截面',
    emptyResults: '运行扫描后生成热图、光谱、效率分解、峰值趋势、近场数据和下载文件。',
    wavelengthAxis: '波长 (um)',
    diameterAxis: '颗粒直径 (um)',
    qscaAxis: '散射效率',
    efficiencyAxis: '效率',
    peakWavelengthAxis: '峰值波长 (um)',
    nearFieldAlt: '近场分布图',
    history: '历史记录',
    jobs: '任务',
    backendUnreachable: '无法连接后端服务。',
    loadJobError: '无法加载任务。',
    csvParseError: '无法解析结果 CSV 文件。',
    autoAdjustedSolver: '扫描网格已按当前求解器限制自动调整。',
    language: '语言',
    zh: '中文',
    en: 'EN',
  },
};

const labels = {
  shape: {
    sphere: { en: 'sphere', zh: '球形' },
    cylinder: { en: 'cylinder', zh: '柱状' },
    cube: { en: 'box', zh: '立方/长方体' },
    ellipsoid: { en: 'ellipsoid', zh: '椭球' },
    shell: { en: 'shell', zh: '壳层' },
  },
  substrate: {
    none: { en: 'None', zh: '无' },
    SiO2: { en: 'SiO2', zh: 'SiO2' },
    glass: { en: 'Glass', zh: '玻璃' },
    metal_film: { en: 'Metal film', zh: '金属薄膜' },
  },
	  solver: {
	    auto: { en: 'Auto', zh: '自动选择' },
	    mie: { en: 'Mie exact', zh: 'Mie 精确解' },
	    tmatrix: { en: 'T-matrix', zh: 'T-matrix' },
	    rcwa: { en: 'RCWA', zh: 'RCWA' },
	    grcwa: { en: 'grcwa', zh: 'grcwa' },
	    smart_proxy: { en: 'Smart proxy', zh: '智能代理' },
	  },
  status: {
    queued: { en: 'queued', zh: '排队中' },
    running: { en: 'running', zh: '运行中' },
    completed: { en: 'completed', zh: '已完成' },
    failed: { en: 'failed', zh: '失败' },
    unknown: { en: 'unknown', zh: '未知' },
  },
  material: {
    TiO2: { en: 'TiO2', zh: 'TiO2' },
    SiO2: { en: 'SiO2', zh: 'SiO2' },
    Au: { en: 'Au', zh: '金 Au' },
    Ag: { en: 'Ag', zh: '银 Ag' },
    Al: { en: 'Al', zh: '铝 Al' },
    glass: { en: 'Glass', zh: '玻璃' },
    polystyrene: { en: 'Polystyrene', zh: '聚苯乙烯' },
    water: { en: 'Water', zh: '水' },
    custom: { en: 'Custom', zh: '自定义' },
  },
};

function tr(language, key) {
  return translations[language]?.[key] ?? translations.en[key] ?? key;
}

function labelFor(language, group, value) {
  return labels[group]?.[value]?.[language] ?? labels[group]?.[value]?.en ?? value;
}

function initialLanguage() {
  const saved = window.localStorage.getItem('fdtd-language');
  if (saved === 'zh' || saved === 'en') return saved;
  return navigator.language?.toLowerCase().startsWith('zh') ? 'zh' : 'en';
}

function updateNested(source, path, value) {
  const parts = path.split('.');
  const next = structuredClone(source);
  let cursor = next;
  for (let index = 0; index < parts.length - 1; index += 1) {
    cursor = cursor[parts[index]];
  }
  cursor[parts.at(-1)] = value;
  return next;
}

function effectiveSolverForDefaults(config) {
  const solver = config.simulation.solver;
  if (solver !== 'auto') return solver;
  if (config.array.enabled) return 'grcwa';
  if (config.substrate.type !== 'none') return 'smart_proxy';
  if (config.geometry.type === 'sphere') return 'mie';
  if (config.geometry.type === 'cylinder' || config.geometry.type === 'shell') return 'tmatrix';
  return 'smart_proxy';
}

function applyScanDefaults(config) {
  const next = structuredClone(config);
  const defaults = SCAN_DEFAULTS[effectiveSolverForDefaults(next)] ?? SCAN_DEFAULTS.auto;
  next.scan.wavelength_points = defaults.wavelength_points;
  next.scan.diameter_points = defaults.diameter_points;
  return next;
}

function clampScanProduct(config, maxPoints) {
  const next = structuredClone(config);
  while (next.scan.wavelength_points * next.scan.diameter_points > maxPoints) {
    if (next.scan.wavelength_points >= next.scan.diameter_points && next.scan.wavelength_points > 2) {
      next.scan.wavelength_points -= 1;
    } else if (next.scan.diameter_points > 2) {
      next.scan.diameter_points -= 1;
    } else {
      break;
    }
  }
  return next;
}

function clampRcwaScan(config) {
  return clampScanProduct(config, RCWA_MAX_SCAN_POINTS);
}

function needsPeriodicSolver(config) {
  return config.array.enabled;
}

function applySolverDefaults(config, solver) {
  const next = applyScanDefaults(updateNested(config, 'simulation.solver', solver));
  if (solver === 'auto' && needsPeriodicSolver(next)) return clampRcwaScan(next);
  if (solver === 'rcwa' || solver === 'grcwa') return clampRcwaScan(next);
  return next;
}

function applyAutoScanDefaults(config) {
  if (config.simulation.solver !== 'auto') return normalizeForInstalledSolvers(config);
  const next = applyScanDefaults(config);
  if (needsPeriodicSolver(next)) return clampRcwaScan(next);
  return next;
}

function normalizeForInstalledSolvers(config) {
  if (config.simulation.solver === 'rcwa' || config.simulation.solver === 'grcwa') return clampRcwaScan(config);
  if (config.simulation.solver === 'auto' && needsPeriodicSolver(config)) return clampRcwaScan(config);
  return config;
}

function formatApiError(errorText, language) {
  try {
    const payload = JSON.parse(errorText);
    const detail = payload.detail;
    if (typeof detail === 'string') return detail;
    if (detail?.message) {
      const notes = detail.solver_selection?.notes;
      const note = Array.isArray(notes) && notes.length > 0 ? ` ${notes.join(' ')}` : '';
      return `${detail.message}${note}`;
    }
  } catch {
    // Fall through to the raw text below.
  }
  return errorText || tr(language, 'backendUnreachable');
}

function Field({ label, value, path, type = 'number', step = '0.1', min, max, onChange, disabled = false }) {
  return (
    <label className="field">
      <span>{label}</span>
      <input
        type={type}
        value={value}
        step={step}
        min={min}
        max={max}
        disabled={disabled}
        onChange={(event) => {
          const raw = type === 'number' ? Number(event.target.value) : event.target.value;
          onChange(path, raw);
        }}
      />
    </label>
  );
}

function SelectField({ label, value, path, options, onChange }) {
  return (
    <label className="field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(path, event.target.value)}>
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}

function ToggleField({ label, checked, path, onChange }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(path, event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function LanguageToggle({ language, onChange }) {
  return (
    <div className="language-toggle" aria-label={tr(language, 'language')}>
      <Languages size={16} />
      <button type="button" className={language === 'zh' ? 'active' : ''} onClick={() => onChange('zh')}>
        {tr(language, 'zh')}
      </button>
      <button type="button" className={language === 'en' ? 'active' : ''} onClick={() => onChange('en')}>
        {tr(language, 'en')}
      </button>
    </div>
  );
}

function GeometryIcon({ type }) {
  const props = { size: 20, strokeWidth: 1.8 };
  if (type === 'sphere') return <Circle {...props} />;
  if (type === 'cube') return <Cuboid {...props} />;
  if (type === 'ellipsoid') return <Box {...props} />;
  if (type === 'shell') return <Layers {...props} />;
  return <Cylinder {...props} />;
}

function geometryDimensions(config) {
  const { size } = config.geometry;
  if (config.geometry.type === 'sphere') {
    return { width: size.diameter, depth: size.diameter, height: size.diameter };
  }
  if (config.geometry.type === 'cube') {
    return { width: size.width, depth: size.depth, height: size.height };
  }
  if (config.geometry.type === 'ellipsoid') {
    return { width: size.diameter, depth: size.width, height: size.height };
  }
  return { width: size.diameter, depth: size.diameter, height: size.height };
}

function previewMetrics(config) {
  const dims = geometryDimensions(config);
  const countX = config.array.enabled ? config.array.count_x : 1;
  const countY = config.array.enabled ? config.array.count_y : 1;
  const spanX = dims.width + (countX - 1) * config.array.period_x;
  const spanZ = dims.depth + (countY - 1) * config.array.period_y;
  const substrateHeight = config.substrate.type !== 'none' ? Math.max(config.substrate.thickness, 0.03) : 0;
  const spanY = dims.height + substrateHeight;
  const radius = Math.max(0.75, Math.sqrt(spanX ** 2 + spanY ** 2 + spanZ ** 2) / 2);
  return { dims, countX, countY, spanX, spanY, spanZ, radius };
}

function cameraDistanceFor(camera, radius) {
  const verticalFov = THREE.MathUtils.degToRad(camera.fov);
  const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * Math.max(camera.aspect, 0.1));
  const fitFov = Math.min(verticalFov, horizontalFov);
  return Math.max(2.4, (radius / Math.sin(fitFov / 2)) * 1.12);
}

function fitPreviewCamera(camera, metrics, target = new THREE.Vector3(0, 0, 0)) {
  const distance = cameraDistanceFor(camera, metrics.radius);
  const direction = new THREE.Vector3(0.82, 0.58, 1).normalize();
  camera.near = Math.max(0.001, metrics.radius / 600);
  camera.far = Math.max(100, distance + metrics.radius * 8);
  camera.position.copy(target).add(direction.multiplyScalar(distance));
  camera.lookAt(target);
  camera.updateProjectionMatrix();
  return {
    minDistance: Math.max(0.35, metrics.radius * 0.45),
    maxDistance: Math.max(distance * 4, metrics.radius * 7),
  };
}

function createParticleGeometry(config) {
  const dims = geometryDimensions(config);
  if (config.geometry.type === 'cube') {
    return new THREE.BoxGeometry(dims.width, dims.height, dims.depth);
  }
  if (config.geometry.type === 'ellipsoid' || config.geometry.type === 'sphere') {
    return new THREE.SphereGeometry(0.5, 48, 32);
  }
  return new THREE.CylinderGeometry(dims.width / 2, dims.width / 2, dims.height, 56);
}

function setArrayInstanceMatrices(instancedMesh, config, metrics, extraScale = new THREE.Vector3(1, 1, 1)) {
  const matrix = new THREE.Matrix4();
  const position = new THREE.Vector3();
  const quaternion = new THREE.Quaternion();
  const scale = config.geometry.type === 'ellipsoid' || config.geometry.type === 'sphere' ? new THREE.Vector3(metrics.dims.width, metrics.dims.height, metrics.dims.depth) : extraScale;
  const offsetX = ((metrics.countX - 1) * config.array.period_x) / 2;
  const offsetZ = ((metrics.countY - 1) * config.array.period_y) / 2;
  let index = 0;
  for (let ix = 0; ix < metrics.countX; ix += 1) {
    for (let iz = 0; iz < metrics.countY; iz += 1) {
      position.set(ix * config.array.period_x - offsetX, metrics.dims.height / 2, iz * config.array.period_y - offsetZ);
      matrix.compose(position, quaternion, scale);
      instancedMesh.setMatrixAt(index, matrix);
      index += 1;
    }
  }
  instancedMesh.instanceMatrix.needsUpdate = true;
}

function createParticleArray(config, material) {
  const metrics = previewMetrics(config);
  const instanceCount = metrics.countX * metrics.countY;
  const group = new THREE.Group();
  if (config.geometry.type === 'shell') {
    const innerDiameter = Math.min(config.geometry.size.inner_diameter, metrics.dims.width * 0.92);
    const outer = new THREE.InstancedMesh(
      new THREE.CylinderGeometry(metrics.dims.width / 2, metrics.dims.width / 2, metrics.dims.height, 48),
      material,
      instanceCount,
    );
    const core = new THREE.InstancedMesh(
      new THREE.CylinderGeometry(innerDiameter / 2, innerDiameter / 2, metrics.dims.height * 1.03, 48),
      new THREE.MeshPhysicalMaterial({
        color: 0x94a3b8,
        transparent: true,
        opacity: 0.42,
        roughness: 0.35,
        metalness: 0.05,
      }),
      instanceCount,
    );
    setArrayInstanceMatrices(outer, config, metrics);
    setArrayInstanceMatrices(core, config, metrics);
    group.add(outer, core);
    return group;
  }
  const particles = new THREE.InstancedMesh(createParticleGeometry(config), material, instanceCount);
  setArrayInstanceMatrices(particles, config, metrics);
  group.add(particles);
  return group;
}

function disposeSceneObject(object) {
  object.traverse?.((item) => {
    item.geometry?.dispose?.();
    if (Array.isArray(item.material)) {
      item.material.forEach((material) => material.dispose?.());
    } else {
      item.material?.dispose?.();
    }
  });
}

function ThreeGeometryPreview({ config, language }) {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const frameRef = useRef(null);
  const viewGroupRef = useRef(null);
  const dragRef = useRef({ active: false, mode: 'rotate', x: 0, y: 0 });
  const configRef = useRef(config);
  const targetRef = useRef(new THREE.Vector3(0, 0, 0));
  const zoomBoundsRef = useRef({ minDistance: 1.4, maxDistance: 9 });

  const fitCurrentView = () => {
    const camera = cameraRef.current;
    if (!camera) return;
    const metrics = previewMetrics(configRef.current);
    zoomBoundsRef.current = fitPreviewCamera(camera, metrics, targetRef.current);
  };

  const resetView = () => {
    if (viewGroupRef.current) viewGroupRef.current.rotation.set(-0.35, 0.45, 0.08);
    targetRef.current.set(0, 0, 0);
    fitCurrentView();
  };

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x11191d);
    const camera = new THREE.PerspectiveCamera(38, mount.clientWidth / mount.clientHeight, 0.01, 100);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const ambient = new THREE.AmbientLight(0xffffff, 0.72);
    const key = new THREE.DirectionalLight(0xffffff, 1.25);
    key.position.set(3, 4, 2);
    const fill = new THREE.DirectionalLight(0x7dd3fc, 0.45);
    fill.position.set(-3, 2, -2);
    scene.add(ambient, key, fill);

    const viewGroup = new THREE.Group();
    viewGroup.rotation.set(-0.35, 0.45, 0.08);
    scene.add(viewGroup);

    sceneRef.current = scene;
    cameraRef.current = camera;
    rendererRef.current = renderer;
    viewGroupRef.current = viewGroup;
    fitCurrentView();

    const animate = () => {
      renderer.render(scene, camera);
      frameRef.current = window.requestAnimationFrame(animate);
    };
    animate();

    const resizeObserver = new ResizeObserver(() => {
      const width = mount.clientWidth || 1;
      const height = mount.clientHeight || 1;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      fitCurrentView();
    });
    resizeObserver.observe(mount);

    const canvas = renderer.domElement;
    const panView = (dx, dy) => {
      const distance = camera.position.distanceTo(targetRef.current);
      const visibleHeight = 2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2) * distance;
      const visibleWidth = visibleHeight * camera.aspect;
      const right = new THREE.Vector3();
      const up = new THREE.Vector3();
      camera.updateMatrixWorld();
      right.setFromMatrixColumn(camera.matrixWorld, 0);
      up.setFromMatrixColumn(camera.matrixWorld, 1);
      const move = right
        .multiplyScalar((-dx / Math.max(canvas.clientWidth, 1)) * visibleWidth)
        .add(up.multiplyScalar((dy / Math.max(canvas.clientHeight, 1)) * visibleHeight));
      camera.position.add(move);
      targetRef.current.add(move);
      camera.lookAt(targetRef.current);
    };
    const onPointerDown = (event) => {
      const mode = event.button === 1 || event.button === 2 || event.shiftKey ? 'pan' : 'rotate';
      dragRef.current = { active: true, mode, x: event.clientX, y: event.clientY };
      canvas.setPointerCapture(event.pointerId);
    };
    const onPointerMove = (event) => {
      if (!dragRef.current.active) return;
      const dx = event.clientX - dragRef.current.x;
      const dy = event.clientY - dragRef.current.y;
      if (dragRef.current.mode === 'pan') {
        panView(dx, dy);
      } else {
        viewGroup.rotation.y += dx * 0.01;
        viewGroup.rotation.x += dy * 0.01;
      }
      dragRef.current = { ...dragRef.current, x: event.clientX, y: event.clientY };
    };
    const onPointerUp = () => {
      dragRef.current.active = false;
    };
    const onWheel = (event) => {
      event.preventDefault();
      const bounds = zoomBoundsRef.current;
      const offset = camera.position.clone().sub(targetRef.current);
      offset.multiplyScalar(event.deltaY > 0 ? 1.08 : 0.92);
      offset.clampLength(bounds.minDistance, bounds.maxDistance);
      camera.position.copy(targetRef.current).add(offset);
      camera.lookAt(targetRef.current);
    };
    const onContextMenu = (event) => {
      event.preventDefault();
    };

    canvas.addEventListener('pointerdown', onPointerDown);
    canvas.addEventListener('pointermove', onPointerMove);
    canvas.addEventListener('pointerup', onPointerUp);
    canvas.addEventListener('pointercancel', onPointerUp);
    canvas.addEventListener('contextmenu', onContextMenu);
    canvas.addEventListener('wheel', onWheel, { passive: false });

    return () => {
      resizeObserver.disconnect();
      canvas.removeEventListener('pointerdown', onPointerDown);
      canvas.removeEventListener('pointermove', onPointerMove);
      canvas.removeEventListener('pointerup', onPointerUp);
      canvas.removeEventListener('pointercancel', onPointerUp);
      canvas.removeEventListener('contextmenu', onContextMenu);
      canvas.removeEventListener('wheel', onWheel);
      if (frameRef.current) window.cancelAnimationFrame(frameRef.current);
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      scene.clear();
    };
  }, []);

  useEffect(() => {
    configRef.current = config;
    const viewGroup = viewGroupRef.current;
    if (!viewGroup) return;
    while (viewGroup.children.length > 0) {
      const child = viewGroup.children[0];
      viewGroup.remove(child);
      disposeSceneObject(child);
    }

    const metrics = previewMetrics(config);
    const dims = metrics.dims;
    const materialPreset = config.material.preset;
    const metalness = ['Au', 'Ag', 'Al'].includes(materialPreset) ? 0.65 : 0.08;
    const particleMaterial = new THREE.MeshPhysicalMaterial({
      color: ['Au', 'Ag', 'Al'].includes(materialPreset) ? 0xd8b45f : 0x2dd4bf,
      roughness: 0.28,
      metalness,
      transparent: config.geometry.type === 'shell',
      opacity: config.geometry.type === 'shell' ? 0.72 : 1,
    });
    viewGroup.add(createParticleArray(config, particleMaterial));

    if (config.substrate.type !== 'none') {
      const substrateWidth = Math.max(dims.width, metrics.spanX) + 0.8;
      const substrateDepth = Math.max(dims.depth, metrics.spanZ) + 0.8;
      const substrate = new THREE.Mesh(
        new THREE.BoxGeometry(substrateWidth, Math.max(config.substrate.thickness, 0.03), substrateDepth),
        new THREE.MeshPhysicalMaterial({
          color: config.substrate.type === 'metal_film' ? 0xb6a06a : 0x9fc7ce,
          transparent: config.substrate.type !== 'metal_film',
          opacity: config.substrate.type === 'metal_film' ? 0.92 : 0.48,
          roughness: 0.22,
          metalness: config.substrate.type === 'metal_film' ? 0.65 : 0.05,
        }),
      );
      substrate.position.y = -Math.max(config.substrate.thickness, 0.03) / 2;
      viewGroup.add(substrate);
    }

    const grid = new THREE.GridHelper(Math.max(3, metrics.spanX, metrics.spanZ) + 1, 12, 0x40606a, 0x263840);
    grid.position.y = -0.02;
    viewGroup.add(grid);
    fitCurrentView();
  }, [config]);

  const dims = geometryDimensions(config);

  return (
    <section className="panel preview-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{tr(language, 'modelCell')}</p>
          <h2>{labelFor(language, 'shape', config.geometry.type)}</h2>
        </div>
        <button className="icon-button" type="button" onClick={resetView} title={tr(language, 'resetView')}>
          <RotateCcw size={17} />
        </button>
      </div>
      <div ref={mountRef} className="preview-canvas" />
      <div className="metric-grid">
        <span>
          <strong>{config.material.name}</strong>
          {tr(language, 'particle')}
        </span>
        <span>
          <strong>{`${dims.width} x ${dims.depth} x ${dims.height}`}</strong>
          um
        </span>
        <span>
          <strong>{config.array.enabled ? `${config.array.count_x}x${config.array.count_y}` : tr(language, 'single')}</strong>
          {tr(language, 'array')}
        </span>
      </div>
    </section>
  );
}

function ParameterPanel({ config, language, onLanguageChange, onConfigChange, onSubmit, isSubmitting, onReset }) {
  const handleChange = (path, value) => {
    if (path === 'simulation.solver') {
      onConfigChange(applySolverDefaults(config, value));
      return;
	    }
	    const next = updateNested(config, path, value);
	    if (path === 'array.enabled' || path === 'substrate.type') {
	      onConfigChange(applyAutoScanDefaults(next));
	      return;
	    }
	    onConfigChange(normalizeForInstalledSolvers(next));
	  };
  const setGeometryType = (type) => {
    const next = updateNested(config, 'geometry.type', type);
    onConfigChange(applyAutoScanDefaults(next));
  };
  const setMaterialPreset = (preset) => {
    const defaults = presetDefaults[preset];
    const next = updateNested(config, 'material.preset', preset);
    next.material.name = defaults.name;
    next.material.n_real = defaults.n_real;
    next.material.n_imag = defaults.n_imag;
    onConfigChange(next);
  };
  const materialLocked = config.material.preset !== 'custom';

  return (
    <aside className="panel controls">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{tr(language, 'fdtdSetup')}</p>
          <h1>{tr(language, 'appTitle')}</h1>
        </div>
        <SlidersHorizontal size={22} />
      </div>
      <div className="language-row">
        <LanguageToggle language={language} onChange={onLanguageChange} />
      </div>

      <div className="control-group">
        <span className="group-label">{tr(language, 'unitShape')}</span>
        <div className="segmented">
          {['sphere', 'cylinder', 'cube', 'ellipsoid', 'shell'].map((type) => (
            <button
              key={type}
              className={config.geometry.type === type ? 'active' : ''}
              type="button"
              onClick={() => setGeometryType(type)}
              title={labelFor(language, 'shape', type)}
            >
              <GeometryIcon type={type} />
              <span>{labelFor(language, 'shape', type)}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="control-grid">
        <Field label={tr(language, 'diameter')} value={config.geometry.size.diameter} path="geometry.size.diameter" min="0.05" onChange={handleChange} />
        <Field label={tr(language, 'height')} value={config.geometry.size.height} path="geometry.size.height" min="0.05" onChange={handleChange} />
        <Field label={tr(language, 'width')} value={config.geometry.size.width} path="geometry.size.width" min="0.05" onChange={handleChange} />
        <Field label={tr(language, 'depth')} value={config.geometry.size.depth} path="geometry.size.depth" min="0.05" onChange={handleChange} />
        {config.geometry.type === 'shell' && (
          <>
            <Field label={tr(language, 'innerDiameter')} value={config.geometry.size.inner_diameter} path="geometry.size.inner_diameter" min="0.02" onChange={handleChange} />
            <Field label={tr(language, 'shellThickness')} value={config.geometry.size.shell_thickness} path="geometry.size.shell_thickness" min="0.01" onChange={handleChange} />
          </>
        )}
      </div>

      <div className="control-group">
        <span className="group-label">{tr(language, 'materialGroup')}</span>
        <div className="control-grid">
          <SelectField
            label={tr(language, 'particleMaterial')}
            value={config.material.preset}
            path="material.preset"
            onChange={(_path, value) => setMaterialPreset(value)}
            options={materialPresets.map((value) => ({ value, label: labelFor(language, 'material', value) }))}
          />
          <Field label={tr(language, 'materialName')} value={config.material.name} path="material.name" type="text" onChange={handleChange} disabled={materialLocked} />
          <Field label={tr(language, 'nReal')} value={config.material.n_real} path="material.n_real" min="0.01" step="0.01" onChange={handleChange} disabled={materialLocked} />
          <Field label={tr(language, 'nImag')} value={config.material.n_imag} path="material.n_imag" min="0" step="0.01" onChange={handleChange} disabled={materialLocked} />
          <Field label={tr(language, 'mediumNReal')} value={config.material.medium_n_real} path="material.medium_n_real" min="0.01" step="0.01" onChange={handleChange} />
          <Field label={tr(language, 'mediumNImag')} value={config.material.medium_n_imag} path="material.medium_n_imag" min="0" step="0.01" onChange={handleChange} />
          {config.geometry.type === 'shell' && (
            <>
              <Field label={tr(language, 'shellCoreNReal')} value={config.material.shell_core_n_real} path="material.shell_core_n_real" min="0.01" step="0.01" onChange={handleChange} />
              <Field label={tr(language, 'shellCoreNImag')} value={config.material.shell_core_n_imag} path="material.shell_core_n_imag" min="0" step="0.01" onChange={handleChange} />
            </>
          )}
        </div>
      </div>

      <div className="control-grid">
        <SelectField
          label={tr(language, 'substrate')}
          value={config.substrate.type}
          path="substrate.type"
          onChange={handleChange}
          options={['none', 'SiO2', 'glass', 'metal_film'].map((value) => ({ value, label: labelFor(language, 'substrate', value) }))}
        />
        <Field label={tr(language, 'substrateThickness')} value={config.substrate.thickness} path="substrate.thickness" min="0" onChange={handleChange} />
        <SelectField
          label={tr(language, 'solver')}
          value={config.simulation.solver}
          path="simulation.solver"
          onChange={handleChange}
          options={ACTIVE_SOLVERS.map((value) => ({ value, label: labelFor(language, 'solver', value) }))}
        />
        <Field label={tr(language, 'spectrumDiameter')} value={config.scan.spectrum_diameter} path="scan.spectrum_diameter" min="0.05" onChange={handleChange} />
      </div>

      <div className="control-group">
        <ToggleField label={tr(language, 'enableArray')} checked={config.array.enabled} path="array.enabled" onChange={handleChange} />
        <div className="control-grid">
          <Field label={tr(language, 'periodX')} value={config.array.period_x} path="array.period_x" min="0.05" onChange={handleChange} />
          <Field label={tr(language, 'periodY')} value={config.array.period_y} path="array.period_y" min="0.05" onChange={handleChange} />
          <Field label={tr(language, 'countX')} value={config.array.count_x} path="array.count_x" min="1" max="100" step="1" onChange={handleChange} />
          <Field label={tr(language, 'countY')} value={config.array.count_y} path="array.count_y" min="1" max="100" step="1" onChange={handleChange} />
        </div>
      </div>

      <div className="control-group">
        <span className="group-label">{tr(language, 'scanRange')}</span>
        <div className="control-grid">
          <Field label={tr(language, 'wavelengthMin')} value={config.scan.wavelength_min} path="scan.wavelength_min" min="0.05" onChange={handleChange} />
          <Field label={tr(language, 'wavelengthMax')} value={config.scan.wavelength_max} path="scan.wavelength_max" min="0.06" onChange={handleChange} />
          <Field label={tr(language, 'wavelengthPoints')} value={config.scan.wavelength_points} path="scan.wavelength_points" min="2" max="600" step="1" onChange={handleChange} />
          <Field label={tr(language, 'diameterPoints')} value={config.scan.diameter_points} path="scan.diameter_points" min="2" max="400" step="1" onChange={handleChange} />
          <Field label={tr(language, 'diameterMin')} value={config.scan.diameter_min} path="scan.diameter_min" min="0.05" onChange={handleChange} />
          <Field label={tr(language, 'diameterMax')} value={config.scan.diameter_max} path="scan.diameter_max" min="0.06" onChange={handleChange} />
        </div>
      </div>

      <div className="button-row">
        <button className="secondary" type="button" onClick={onReset}>
          <RotateCcw size={17} />
          {tr(language, 'reset')}
        </button>
        <button className="primary" type="button" onClick={onSubmit} disabled={isSubmitting}>
          <Play size={17} />
          {isSubmitting ? tr(language, 'runningAction') : tr(language, 'runScan')}
        </button>
      </div>
    </aside>
  );
}

function ResultsPanel({ language, job, files, heatmapData, spectrumData, efficiencyData, peakData, onRefresh }) {
  const imageFile = (name) => files.find((file) => file.name === name);
  const downloadUrl = (file) => `${API_BASE}${file.url}`;
  const status = job ? labelFor(language, 'status', job.status) : tr(language, 'noJob');

  return (
    <section className="panel results-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">{tr(language, 'results')}</p>
          <h2>{status}</h2>
        </div>
        <button className="icon-button" type="button" onClick={onRefresh} title={tr(language, 'refreshJobs')}>
          <RefreshCw size={18} />
        </button>
      </div>

      {job ? (
        <>
          <div className="progress-shell">
            <div className="progress-bar" style={{ width: `${Math.round((job.progress ?? 0) * 100)}%` }} />
          </div>
          {job.error && <p className="error-text">{job.error}</p>}
          {job.summary && (
            <>
              <div className="summary-grid">
                <span>
                  <strong>{job.summary.global_peak?.wavelength_um?.toFixed(3)} um</strong>
                  {tr(language, 'globalPeakWl')}
                </span>
                <span>
                  <strong>{job.summary.global_peak?.diameter_um?.toFixed(3)} um</strong>
                  {tr(language, 'globalPeakD')}
                </span>
                <span>
                  <strong>{job.summary.spectrum_peak?.cross_section_um2?.toFixed(3)}</strong>
                  {tr(language, 'crossSection')}
                </span>
              </div>
            </>
          )}
        </>
      ) : (
        <div className="empty-state">
          <ScanLine size={42} />
          <p>{tr(language, 'emptyResults')}</p>
        </div>
      )}

      {heatmapData && (
        <Plot
          className="plot"
          data={[
            {
              x: heatmapData.wavelengths,
              y: heatmapData.diameters,
              z: heatmapData.values,
              type: 'heatmap',
              colorscale: 'Rainbow',
              zsmooth: 'best',
              colorbar: { title: tr(language, 'qscaAxis') },
            },
          ]}
          layout={{
            autosize: true,
            margin: { l: 55, r: 20, t: 20, b: 48 },
            xaxis: { title: tr(language, 'wavelengthAxis') },
            yaxis: { title: tr(language, 'diameterAxis') },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
          }}
          useResizeHandler
          config={{ displaylogo: false, responsive: true }}
        />
      )}

      {spectrumData && (
        <Plot
          className="plot small"
          data={[
            {
              x: spectrumData.wavelengths,
              y: spectrumData.qsca,
              type: 'scatter',
              mode: 'lines',
              name: 'Qsca',
              line: { color: '#0f766e', width: 3 },
            },
          ]}
          layout={{
            autosize: true,
            margin: { l: 55, r: 20, t: 12, b: 48 },
            xaxis: { title: tr(language, 'wavelengthAxis') },
            yaxis: { title: tr(language, 'qscaAxis') },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
          }}
          useResizeHandler
          config={{ displaylogo: false, responsive: true }}
        />
      )}

      {efficiencyData && (
        <Plot
          className="plot small"
          data={[
            { x: efficiencyData.wavelengths, y: efficiencyData.qsca, type: 'scatter', mode: 'lines', name: 'Qsca', line: { color: '#0f766e', width: 2.5 } },
            { x: efficiencyData.wavelengths, y: efficiencyData.qabs, type: 'scatter', mode: 'lines', name: 'Qabs', line: { color: '#b45309', width: 2.5 } },
            { x: efficiencyData.wavelengths, y: efficiencyData.qext, type: 'scatter', mode: 'lines', name: 'Qext', line: { color: '#334155', width: 2.5 } },
          ]}
          layout={{
            autosize: true,
            margin: { l: 55, r: 20, t: 12, b: 48 },
            xaxis: { title: tr(language, 'wavelengthAxis') },
            yaxis: { title: tr(language, 'efficiencyAxis') },
            legend: { orientation: 'h' },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
          }}
          useResizeHandler
          config={{ displaylogo: false, responsive: true }}
        />
      )}

      {peakData && (
        <Plot
          className="plot small"
          data={[
            {
              x: peakData.diameters,
              y: peakData.peakWavelengths,
              type: 'scatter',
              mode: 'lines+markers',
              line: { color: '#6d5dfc', width: 2.5 },
              marker: { size: 5 },
            },
          ]}
          layout={{
            autosize: true,
            margin: { l: 55, r: 20, t: 12, b: 48 },
            xaxis: { title: tr(language, 'diameterAxis') },
            yaxis: { title: tr(language, 'peakWavelengthAxis') },
            paper_bgcolor: 'rgba(0,0,0,0)',
            plot_bgcolor: 'rgba(0,0,0,0)',
          }}
          useResizeHandler
          config={{ displaylogo: false, responsive: true }}
        />
      )}

      {imageFile('fig_field_xy.png') && (
        <div className="field-image">
          <img src={downloadUrl(imageFile('fig_field_xy.png'))} alt={tr(language, 'nearFieldAlt')} />
        </div>
      )}

      {files.length > 0 && (
        <div className="downloads">
          {files.map((file) => (
            <a key={file.name} href={downloadUrl(file)} download>
              <Download size={15} />
              {file.name}
            </a>
          ))}
        </div>
      )}
    </section>
  );
}

function HistoryPanel({ language, jobs, activeJobId, onSelect }) {
  return (
    <section className="panel history">
      <div className="panel-heading compact">
        <div>
          <p className="eyebrow">{tr(language, 'history')}</p>
          <h2>{tr(language, 'jobs')}</h2>
        </div>
      </div>
      <div className="job-list">
        {jobs.map((job) => (
          <button key={job.job_id} type="button" className={job.job_id === activeJobId ? 'active' : ''} onClick={() => onSelect(job.job_id)}>
            <span>{job.name}</span>
            <strong>{labelFor(language, 'status', job.status)}</strong>
          </button>
        ))}
      </div>
    </section>
  );
}

function parseCsvRows(text) {
  const rows = text.trim().split(/\r?\n/).map((row) => row.split(','));
  const header = rows[0];
  return rows.slice(1).map((row) => Object.fromEntries(header.map((name, index) => [name, row[index]])));
}

function parseHeatmapCsv(text) {
  const rows = text.trim().split(/\r?\n/).map((row) => row.split(','));
  const wavelengths = rows[0].slice(1).map(Number);
  const diameters = [];
  const values = [];
  for (const row of rows.slice(1)) {
    diameters.push(Number(row[0]));
    values.push(row.slice(1).map(Number));
  }
  return { wavelengths, diameters, values };
}

function parseSpectrumCsv(text) {
  const rows = parseCsvRows(text);
  return {
    wavelengths: rows.map((row) => Number(row.wavelength_um)),
    qsca: rows.map((row) => Number(row.scattering_efficiency)),
    qabs: rows.map((row) => Number(row.absorption_efficiency ?? 0)),
    qext: rows.map((row) => Number(row.extinction_efficiency ?? row.scattering_efficiency)),
  };
}

function parsePeaksCsv(text) {
  const rows = parseCsvRows(text);
  return {
    diameters: rows.map((row) => Number(row.diameter_um)),
    peakWavelengths: rows.map((row) => Number(row.peak_wavelength_um)),
  };
}

function App() {
  const [language, setLanguage] = useState(initialLanguage);
  const [config, setConfig] = useState(defaultConfig);
  const [jobs, setJobs] = useState([]);
  const [activeJobId, setActiveJobId] = useState(null);
  const [activeJob, setActiveJob] = useState(null);
  const [files, setFiles] = useState([]);
  const [heatmapData, setHeatmapData] = useState(null);
  const [spectrumData, setSpectrumData] = useState(null);
  const [efficiencyData, setEfficiencyData] = useState(null);
  const [peakData, setPeakData] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [message, setMessage] = useState('');

  useEffect(() => {
    window.localStorage.setItem('fdtd-language', language);
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
  }, [language]);

  const loadJobs = async () => {
    const response = await fetch(`${API_BASE}/api/simulations`);
    if (!response.ok) return;
    const payload = await response.json();
    setJobs(payload.jobs ?? []);
  };

  const loadJob = async (jobId) => {
    if (!jobId) return;
    const response = await fetch(`${API_BASE}/api/simulations/${jobId}`);
    if (!response.ok) return;
    const payload = await response.json();
    setActiveJob(payload);
    if (payload.status === 'completed') {
      const resultsResponse = await fetch(`${API_BASE}/api/simulations/${jobId}/results`);
      if (resultsResponse.ok) {
        const resultsPayload = await resultsResponse.json();
        setFiles(resultsPayload.files ?? []);
      }
    } else {
      setFiles([]);
      setHeatmapData(null);
      setSpectrumData(null);
      setEfficiencyData(null);
      setPeakData(null);
    }
  };

  useEffect(() => {
    loadJobs().catch(() => setMessage(tr(language, 'backendUnreachable')));
  }, [language]);

  useEffect(() => {
    if (!activeJobId) return undefined;
    loadJob(activeJobId).catch(() => setMessage(tr(language, 'loadJobError')));
    const interval = window.setInterval(() => {
      loadJob(activeJobId).catch(() => {});
      loadJobs().catch(() => {});
    }, activeJob?.status === 'running' || activeJob?.status === 'queued' ? 1200 : 4000);
    return () => window.clearInterval(interval);
  }, [activeJobId, activeJob?.status, language]);

  useEffect(() => {
    const loadCsv = async () => {
      const heatmap = files.find((file) => file.name === 'heatmap.csv');
      const spectrum = files.find((file) => file.name === 'spectrum.csv');
      const peaks = files.find((file) => file.name === 'peaks.csv');
      if (heatmap) {
        const text = await fetch(`${API_BASE}${heatmap.url}`).then((response) => response.text());
        setHeatmapData(parseHeatmapCsv(text));
      }
      if (spectrum) {
        const text = await fetch(`${API_BASE}${spectrum.url}`).then((response) => response.text());
        const parsed = parseSpectrumCsv(text);
        setSpectrumData(parsed);
        setEfficiencyData(parsed);
      }
      if (peaks) {
        const text = await fetch(`${API_BASE}${peaks.url}`).then((response) => response.text());
        setPeakData(parsePeaksCsv(text));
      }
    };
    loadCsv().catch(() => setMessage(tr(language, 'csvParseError')));
  }, [files, language]);

  const submit = async () => {
    setIsSubmitting(true);
    setMessage('');
    setHeatmapData(null);
    setSpectrumData(null);
    setEfficiencyData(null);
    setPeakData(null);
    setFiles([]);
    try {
      const payload = structuredClone(config);
      if (!payload.array.enabled) {
        payload.array.count_x = 1;
        payload.array.count_y = 1;
      }
      const normalizedPayload = normalizeForInstalledSolvers(payload);
      if (
        normalizedPayload.scan.wavelength_points !== payload.scan.wavelength_points ||
        normalizedPayload.scan.diameter_points !== payload.scan.diameter_points
      ) {
        setConfig(normalizedPayload);
        setMessage(tr(language, 'autoAdjustedSolver'));
      }
      const response = await fetch(`${API_BASE}/api/simulations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(normalizedPayload),
      });
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(formatApiError(errorText, language));
      }
      const created = await response.json();
      setActiveJobId(created.job_id);
      await loadJobs();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="app-shell">
      <ParameterPanel
        config={config}
        language={language}
        onLanguageChange={setLanguage}
        onConfigChange={setConfig}
        onSubmit={submit}
        isSubmitting={isSubmitting}
        onReset={() => setConfig(defaultConfig)}
      />
      <div className="center-column">
        <ThreeGeometryPreview config={config} language={language} />
        <HistoryPanel language={language} jobs={jobs} activeJobId={activeJobId} onSelect={setActiveJobId} />
      </div>
      <ResultsPanel
        language={language}
        job={activeJob}
        files={files}
        heatmapData={heatmapData}
        spectrumData={spectrumData}
        efficiencyData={efficiencyData}
        peakData={peakData}
        onRefresh={loadJobs}
      />
      {message && <div className="toast">{message}</div>}
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
