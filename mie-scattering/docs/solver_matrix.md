# Solver matrix

Only installed and integrated solvers are exposed through the API and UI. The
active solver set is:

- `mie`: homogeneous isolated sphere Mie solution via `miepython`.
- `tmatrix`: `treams` T-matrix adapter for isolated sphere, cylinder, and shell
  models covered by the current adapter.
- `rcwa`: `rcwa` periodic-unit-cell adapter for enabled array models.
- `grcwa`: `grcwa` periodic-unit-cell adapter for enabled array models.
- `meep`: Meep FDTD backend, kept available only for explicit finite-domain runs.
- `auto`: chooses among the lighter integrated solvers by model scope and avoids
  Meep by default.
- `smart_proxy`: equivalent-sphere approximation used as the low-resource auto
  fallback.

## Current integrated behavior

| Model scope | Auto behavior | Current solver | Guardrails |
| --- | --- | --- | --- |
| Isolated homogeneous sphere, no substrate, no array, lossless ambient | Runs Mie | `mie` | Requires `miepython` |
| Isolated sphere/cylinder/shell outside exact Mie scope | Runs T-matrix where covered | `tmatrix` | No substrate; non-absorbing ambient |
| Enabled periodic array | Runs periodic-unit-cell RCWA | `grcwa` | Max 96 wavelength-diameter scan points |
| Explicit periodic array with `simulation.solver="rcwa"` | Runs periodic-unit-cell RCWA | `rcwa` | Max 96 wavelength-diameter scan points |
| Ellipsoid/cube without array | Falls through to low-resource proxy | `smart_proxy` | Avoids automatic Meep jobs |
| Any non-array model with substrate | Falls through to low-resource proxy | `smart_proxy` | Avoids automatic Meep jobs |
| Too-large RCWA scan | Blocks with adjustment note | None | Reduce wavelength_points * diameter_points to 96 or lower |
| Explicit Meep scan | Runs only when requested directly | `meep` when accepted | Reduce wavelength_points * diameter_points to 288 or lower |

## Default Scan Density

| Solver path | Default wavelength points | Default diameter points |
| --- | ---: | ---: |
| `mie`, `smart_proxy`, auto sphere | 160 | 80 |
| `tmatrix`, auto cylinder/shell | 100 | 50 |
| `rcwa`, `grcwa`, auto enabled array | 12 | 8 |
| `smart_proxy`, auto cube/ellipsoid/substrate fallback | 160 | 80 |
| explicit `meep` | 12 | 6 |

## Solver selection rules

### Sphere

Use `mie` first for homogeneous, isolated spheres in a non-absorbing medium. If
the model is still isolated but outside the exact Mie route, explicit `tmatrix`
uses `treams.TMatrix.sphere`.

### Cylinder And Shell

Use `tmatrix` for isolated cylinder-like models covered by
`treams.TMatrixC.cylinder`. The current project shell geometry is cylindrical,
so shell uses the multi-layer cylindrical T-matrix path.

### Arrays

Use `grcwa` by default for enabled arrays. `rcwa` is also exposed explicitly.
Both adapters model a periodic unit cell, not a finite cluster. Shape cross
sections are rasterized to a transverse permittivity grid; sphere and ellipsoid
models are sliced into multiple layers.

### Meep

Meep remains available for explicit finite-domain FDTD jobs only. Auto routing
does not select Meep; if no lighter exact adapter is applicable, auto uses
`smart_proxy` instead. Explicit Meep jobs are still resource guarded.

## Not Integrated

- BEM: `bempp-cl`, SCUFF-EM, or MNPBEM-style finite-particle/interface adapter.
- DDA: ADDA-style voxelized arbitrary-shape adapter.

## Source anchors

- `miepython`: https://miepython.readthedocs.io/.
- `treams`: https://github.com/tfp-photonics/treams.
- `rcwa`: https://github.com/edmundsj/RCWA.
- `grcwa`: https://github.com/weiliangjinca/grcwa.
- Meep: https://meep.readthedocs.io/.
- SCUFF-EM: https://homerreid.github.io/scuff-em-documentation/reference/TopLevel/.
- ADDA: https://github.com/adda-team/adda.
