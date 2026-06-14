from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


GeometryType = Literal["sphere", "cylinder", "cube", "ellipsoid", "shell"]
SubstrateType = Literal["none", "SiO2", "glass", "metal_film"]
MaterialPreset = Literal["TiO2", "SiO2", "Au", "Ag", "Al", "glass", "polystyrene", "water", "custom"]
SolverMode = Literal["auto", "mie", "tmatrix", "rcwa", "grcwa", "smart_proxy", "meep"]


class GeometrySize(BaseModel):
    diameter: float = Field(0.8, gt=0, description="Primary particle diameter in micrometers.")
    height: float = Field(0.45, gt=0, description="Height for cylinder, cube, ellipsoid, or shell.")
    width: float = Field(0.8, gt=0, description="Width used by cube and ellipsoid.")
    depth: float = Field(0.8, gt=0, description="Depth used by cube and ellipsoid.")
    inner_diameter: float = Field(0.45, gt=0, description="Inner diameter for shell geometry.")
    shell_thickness: float = Field(0.175, gt=0, description="Shell thickness in micrometers.")


class GeometryConfig(BaseModel):
    type: GeometryType = "sphere"
    size: GeometrySize = Field(default_factory=GeometrySize)

    @model_validator(mode="after")
    def validate_shell(self) -> "GeometryConfig":
        if self.type == "shell" and self.size.inner_diameter >= self.size.diameter:
            raise ValueError("Shell inner_diameter must be smaller than diameter")
        return self


class MaterialConfig(BaseModel):
    preset: MaterialPreset = "TiO2"
    name: str = Field("TiO2", min_length=1, max_length=80)
    n_real: float = Field(2.40, gt=0.0)
    n_imag: float = Field(0.0, ge=0.0)
    medium_n_real: float = Field(1.0, gt=0.0)
    medium_n_imag: float = Field(0.0, ge=0.0)
    shell_core_n_real: float = Field(1.45, gt=0.0)
    shell_core_n_imag: float = Field(0.0, ge=0.0)


class SubstrateConfig(BaseModel):
    type: SubstrateType = "none"
    thickness: float = Field(0.5, ge=0)
    metal_index_real: float = Field(0.18, ge=0)
    metal_index_imag: float = Field(3.45, ge=0)


class ArrayConfig(BaseModel):
    enabled: bool = False
    period_x: float = Field(1.2, gt=0)
    period_y: float = Field(1.2, gt=0)
    count_x: int = Field(1, ge=1, le=100)
    count_y: int = Field(1, ge=1, le=100)

    @model_validator(mode="after")
    def normalize_counts(self) -> "ArrayConfig":
        if not self.enabled:
            self.count_x = 1
            self.count_y = 1
        return self


class ScanConfig(BaseModel):
    wavelength_min: float = Field(0.3, gt=0)
    wavelength_max: float = Field(2.5, gt=0)
    wavelength_points: int = Field(24, ge=2, le=600)
    diameter_min: float = Field(0.3, gt=0)
    diameter_max: float = Field(2.5, gt=0)
    diameter_points: int = Field(12, ge=2, le=400)
    spectrum_diameter: float = Field(0.9, gt=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "ScanConfig":
        if self.wavelength_max <= self.wavelength_min:
            raise ValueError("wavelength_max must be greater than wavelength_min")
        if self.diameter_max <= self.diameter_min:
            raise ValueError("diameter_max must be greater than diameter_min")
        return self


class SimulationSettings(BaseModel):
    solver: SolverMode = "auto"
    resolution: int = Field(24, ge=8, le=120)
    pml_thickness: float = Field(0.6, gt=0)
    runtime: float = Field(180.0, gt=0)
    cell_padding: float = Field(1.0, ge=0.2)
    meep_workers: int = Field(1, ge=1, le=2)
    random_seed: int = Field(7, ge=0)


class SimulationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field("Nanoparticle scattering study", min_length=1, max_length=120)
    geometry: GeometryConfig = Field(default_factory=GeometryConfig)
    material: MaterialConfig = Field(default_factory=MaterialConfig)
    substrate: SubstrateConfig = Field(default_factory=SubstrateConfig)
    array: ArrayConfig = Field(default_factory=ArrayConfig)
    scan: ScanConfig = Field(default_factory=ScanConfig)
    simulation: SimulationSettings = Field(default_factory=SimulationSettings)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        return value.strip()
