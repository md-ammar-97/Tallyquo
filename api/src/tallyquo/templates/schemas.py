from uuid import UUID

from pydantic import BaseModel


class TemplateOut(BaseModel):
    id: UUID
    name: str
    schema_version: int
    version: int
    theme: dict
    blocks: list[str]
    is_system: bool
    is_default: bool
    tenant_id: UUID | None


class TemplatePackage(BaseModel):
    """The portable .json format (implementation_plan.md 4.1). A package
    is schema-versioned independently of the DB row's own `schema_version`
    -- `package_schema_version` describes *this file's own shape*, so a
    future breaking change to the export format doesn't require a
    matching migration of every already-exported file sitting on
    someone's disk."""

    package_schema_version: int
    name: str
    theme: dict
    blocks: list[str]


class SetDefaultTemplateIn(BaseModel):
    template_id: UUID


class TemplateIn(BaseModel):
    """4.2: create or update a tenant-owned custom template."""

    name: str
    theme: dict
    blocks: list[str]


class TemplatePreviewIn(BaseModel):
    theme: dict
    blocks: list[str]
