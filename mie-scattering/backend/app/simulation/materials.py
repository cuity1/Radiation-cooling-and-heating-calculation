from __future__ import annotations

from dataclasses import dataclass

from app.models import MaterialConfig


@dataclass(frozen=True)
class Material:
    name: str
    refractive_index: complex
    source: str

    @property
    def epsilon(self) -> complex:
        return self.refractive_index * self.refractive_index

    def to_summary(self) -> dict[str, object]:
        return {
            "name": self.name,
            "n_real": float(self.refractive_index.real),
            "n_imag": float(self.refractive_index.imag),
            "epsilon_real": float(self.epsilon.real),
            "epsilon_imag": float(self.epsilon.imag),
            "source": self.source,
        }


PRESET_MATERIALS: dict[str, Material] = {
    "TiO2": Material("TiO2", 2.40 + 0.0j, "constant preset"),
    "SiO2": Material("SiO2", 1.46 + 0.0j, "constant preset"),
    "Au": Material("Au", 0.18 + 3.45j, "constant preset"),
    "Ag": Material("Ag", 0.14 + 3.98j, "constant preset"),
    "Al": Material("Al", 1.44 + 7.38j, "constant preset"),
    "glass": Material("glass", 1.52 + 0.0j, "constant preset"),
    "polystyrene": Material("polystyrene", 1.59 + 0.0j, "constant preset"),
    "water": Material("water", 1.33 + 0.0j, "constant preset"),
}


SUBSTRATE_MATERIALS = {
    "SiO2": PRESET_MATERIALS["SiO2"],
    "glass": PRESET_MATERIALS["glass"],
}


def resolve_particle_material(config: MaterialConfig) -> Material:
    if config.preset == "custom":
        return Material(config.name, complex(config.n_real, config.n_imag), "custom input")
    return PRESET_MATERIALS[config.preset]


def resolve_medium_material(config: MaterialConfig) -> Material:
    return Material("ambient medium", complex(config.medium_n_real, config.medium_n_imag), "custom input")


def resolve_shell_core_material(config: MaterialConfig) -> Material:
    return Material("shell core", complex(config.shell_core_n_real, config.shell_core_n_imag), "custom input")


def substrate_index(name: str, metal_real: float, metal_imag: float) -> complex:
    if name == "none":
        return 1.0 + 0.0j
    if name == "metal_film":
        return complex(metal_real, metal_imag)
    return SUBSTRATE_MATERIALS[name].refractive_index


def material_summary(config: MaterialConfig, substrate_type: str, substrate_n: complex) -> dict[str, object]:
    particle = resolve_particle_material(config)
    medium = resolve_medium_material(config)
    shell_core = resolve_shell_core_material(config)
    return {
        "particle": particle.to_summary(),
        "medium": medium.to_summary(),
        "shell_core": shell_core.to_summary(),
        "substrate": {
            "name": substrate_type,
            "n_real": float(substrate_n.real),
            "n_imag": float(substrate_n.imag),
            "source": "configured substrate",
        },
    }
