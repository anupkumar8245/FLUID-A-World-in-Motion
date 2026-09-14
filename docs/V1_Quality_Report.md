# V1 completion and review

## Delivered scope

Blender 5.1.2 environment built from a blank scene, four reusable .blend files, five Geometry Nodes groups, a 30-second camera path, four Blender stills, an Unreal still, and a 30-second review movie. Portable export contains 21 scene meshes plus one calibration mesh, two base-color textures, and 2,141 placement records.

Unreal 5.8.1 implementation contains a separate L_AbyssalGarden map, native flying navigation, an LS_V1_Descent sequence, instanced mesh groups, recreated materials, lights and volumetric atmosphere. The ScientificRenderer and WebGPU projects were not modified for this slice. The existing OceanEnvironment.blend is preserved.

## Visual review and corrections

1. Initial water haze flattened the composition. Reduced Blender volume density from 0.013 to 0.007, lowered light levels, and changed exposure to -0.2. Rechecked entrance, garden, threshold and navigation views.
2. Cliffs appeared too coarse. Increased source mesh subdivision and added finer erosion and procedural bump detail. The main silhouettes and route remained intact.
3. Luminous tips repeated a conical shape. Replaced them with rounded tips and varied their proportions. Further silhouette variety remains useful for later art refinement.

The first Unreal image was overexposed. Reduced engine light intensities, set manual exposure, and added a low atmospheric fill. Reviewed the corrected frame. Unreal is a separate presentation of the scene; shader parity with Cycles is not claimed. The Unreal capture still shows noisier highlights and thinner plant detail than the offline Blender renders.

## Evidence

- Blender source reopened and textures were readable after the power cut; delivery copy reopened again after packaging.
- Sampled 60 camera locations with 1-meter nearest-surface clearance and 39 central navigation points with 0.5-meter clearance: all passed. These are sampled surface checks, not a complete swept-volume or interior test.
- Unreal FBX calibration box center: approximately (300, -500, 700) centimeters for Blender (3, 5, 7) meters.
- Unreal assembled placement count: 2,141 across 21 instanced mesh components.
- Unreal Play-in-Editor: DefaultPawn spawned at (-300, 3000, 800) centimeters and moved 3,382.86 centimeters during the automated forward movement interval. Floor visibility trace returned a blocking hit.
- Instanced-material usage flags saved; actor roots and mesh components set to static mobility. Final map was reopened for the navigation test.
- Review video: H.264, 960×540, 12 fps, 360 frames, 30.000 seconds. FFmpeg decoded the entire file without reporting errors.
- Still renders: entrance 6.44 s, garden 7.00 s, threshold 6.18 s, navigation 6.43 s at 1440×810, 64 Cycles samples, GPU mode.
- After the power cut, movie recovery reused 96 complete PNGs and rendered 264 frames in 595.21 seconds. The renderer verifies PNG chunk checksums before reusing a frame. Timing excludes the interrupted earlier run.

Destination installation is verified separately in installation.json and installed_unreal_validation.json after copying into the requested project paths. Copy hashes are checked before destination reimport metadata is updated.

## Practical limits

This is a stylized first vertical slice. Production realism, final material baking, broader exploration coverage, complete collision-route testing, packaged-game testing and target-device FPS profiling remain future work. No real-time FPS benchmark is claimed. The review movie is 12 fps; the editable source and Unreal sequence remain 24 fps. No full-resolution final cinematic video is included.

Blender procedural bump is not yet baked into Unreal normal maps. Family .blend files are snapshots rather than live-linked dependencies. Decorative vegetation has no collision; solid rock, terrain and ring collision uses detailed static meshes rather than an optimized simulation-boundary representation. Scientific correctness is not applicable to these purely artistic effects; no solver is implemented.

The shutdown damaged transient material packages and some partial frame files. They were rebuilt from the saved source; the damaged validation packages were kept outside the Content directory as a recovery backup.
