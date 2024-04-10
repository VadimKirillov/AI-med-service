import * as THREE from 'https://unpkg.com/three@0.138.3/build/three.module.js';
import { OrbitControls } from 'https://unpkg.com/three@0.138.3/examples/jsm/controls/OrbitControls.js';
import { EffectComposer } from 'https://unpkg.com/three@0.138.3/examples/jsm/postprocessing/EffectComposer.js';
import { RenderPass } from 'https://unpkg.com/three@0.138.3/examples/jsm/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'https://unpkg.com/three@0.138.3/examples/jsm/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'https://unpkg.com/three@0.138.3/examples/jsm/postprocessing/ShaderPass.js';

/**
 * Sizes
 */
const canvasContainer = document.querySelector('.canvas-container');

const sizes = {
    width: canvasContainer.offsetWidth,
    height: canvasContainer.offsetHeight
}
let renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(sizes.width, sizes.height);

// Добавляем канву в документ
document.body.appendChild(renderer.domElement)
renderer.setSize(sizes.width, sizes.height)

// Функция для обновления размеров канвас при изменении размеров окна
function updateCanvasSize() {
    sizes.width = canvasContainer.offsetWidth;
    sizes.height = canvasContainer.offsetHeight;
    renderer.setSize(sizes.width, sizes.height);
}

// Добавляем обработчик события для обновления размеров канвас при изменении размеров окна

/**
 * Base
 */



// Scene
const scene = new THREE.Scene()
scene.background = new THREE.Color("black");

/**
 * Test mesh
 */
// Geometry
const geometry = new THREE.PlaneGeometry(1, 1, 15, 15)
geometry.rotateX(Math.PI/2);
const edges = new THREE.EdgesGeometry( geometry );

// Shaders
const vertexShader = document.querySelector('#vertexshader' ).textContent;
const lineShader = document.querySelector('#fragment-line' ).textContent;
const dotShader = document.querySelector('#fragment-dot' ).textContent;
const gridShader = document.querySelector('#fragment-grid' ).textContent;

// Material

const dotMat = new THREE.ShaderMaterial({
  side:THREE.DoubleSide,
  transparent:true,
  uniforms:{
    uTime:{ value:0 },
  },
  vertexShader: vertexShader,
	fragmentShader: dotShader,
})

const lineMat = new THREE.ShaderMaterial({
  side:THREE.DoubleSide,
  transparent:true,
  uniforms:{
    uTime:{ value:0 },
    uColor:{value:new THREE.Vector3(0.16, 0.94, 0.37)}
  },
  vertexShader: vertexShader,
	fragmentShader: lineShader,
})

const gridMat = new THREE.ShaderMaterial({
  side:THREE.DoubleSide,
  transparent:true,
  uniforms:{
    uTime:{ value:0 },
  },
  vertexShader: vertexShader,
	fragmentShader: gridShader,
})



const dots = new THREE.Mesh(geometry, dotMat);
dots.position.y = 3 / 2.5 - .5;

const lines1 = new THREE.Mesh(geometry, lineMat);
lines1.position.y = 2 / 2.5 - .5;
lines1.rotation.y = 1 * Math.PI/2;


const lines2 = new THREE.Mesh(geometry, lineMat.clone());
lines2.position.y = 1 / 2.5 - .5;
lines2.material.uniforms.uColor.value = new THREE.Vector3(0.82, 0.16, 0.94);


const grids = new THREE.Mesh(geometry, gridMat);
grids.position.y = 0 / 2.5 - .5;


scene.add(dots,lines1,lines2,grids)



/**
 * Camera
 */
// Base camera
const camera = new THREE.OrthographicCamera( -1.5, 1.5, sizes.height/sizes.width * 1.5 , sizes.height/sizes.width * -1.5, 1.5, 1000 );
camera.position.set(3,3,3)

// camera.rotation.y=(Math.PI/2)
scene.add(camera)

// Controls
const controls = new OrbitControls(camera, renderer.domElement)
controls.enableDamping = true


/**
 * PostProcessing
 */
let renderScene = new RenderPass( scene, camera );
const scanlinesShader = {

	name: 'scanlinesShader',

	uniforms: {

		'tDiffuse': { value: null },
		'opacity': { value: 1.0 }

	},

	vertexShader: /* glsl */`

		varying vec2 vUv;

		void main() {

			vUv = uv;
			gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );

		}`,

	fragmentShader: /* glsl */`

		uniform float opacity;

		uniform sampler2D tDiffuse;

		varying vec2 vUv;

		void main() {
      gl_FragColor = texture2D( tDiffuse, vUv );
      float strength = step(.2, mod(vUv.y * 10.,1.));

      vec4 scanlines = clamp(vec4(mod((vUv.y * 400.0), 2.4)), 0.2, 1.0) * 0.4 + 0.6;
      gl_FragColor *= scanlines;
		}`

};
const scanlinesPass = new ShaderPass( scanlinesShader );


let bloomPass = new UnrealBloomPass(
				new THREE.Vector2( window.innerWidth, window.innerHeight ),
				.9, .9, 0.1
		);


let composer = new EffectComposer( renderer );
		composer.addPass( renderScene );
		composer.addPass( bloomPass );
    composer.addPass( scanlinesPass );







/**
 * Animate
 */
const clock = new THREE.Clock();
const tick = () =>
{
    // Update controls
    controls.update()
    const elapsedTime = clock.getElapsedTime()
    dotMat.uniforms.uTime.value =
    lineMat.uniforms.uTime.value =
    lines2.material.uniforms.uTime.value =
    gridMat.uniforms.uTime.value = elapsedTime;

    // Render
    composer.render(scene, camera)

    // Call tick again on the next frame
    window.requestAnimationFrame(tick)
}

tick()


window.addEventListener('resize', () =>
{
    // Update sizes
    sizes.width = canvasContainer.offsetWidth;
    sizes.height = canvasContainer.offsetHeight;
    renderer.setSize(sizes.width, sizes.height);

    // Update camera
    camera.top = sizes.height / sizes.width * 1.5 ;
    camera.bottom = sizes.height / sizes.width * -1.5 ;
    camera.updateProjectionMatrix()


    // Update renderer

    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
})