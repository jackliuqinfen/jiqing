"""Versioned semantic extraction schemas for Phase 1 documents."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionSchema:
    version: str
    document_type: str
    field_types: dict[str, str]

    @property
    def semantic_keys(self):
        return frozenset(self.field_types)


_CONTRACT_FIELDS = {
    "project.name": "text",
    "party.owner": "organization",
    "party.contractor": "organization",
    "contract.number": "text",
    "contract.type": "text",
    "contract.amount": "money",
    "contract.signed_date": "date",
    "contract.start_date": "date",
    "contract.end_date": "date",
    "project.manager": "person",
    "contract.payment_terms": "clauses",
    "contract.retention_terms": "clauses",
    "contract.performance_bond_terms": "clauses",
}

_ACCEPTANCE_FIELDS = {
    "project.name": "text",
    "party.contractor": "organization",
    "party.supervisor": "organization",
    "party.designer": "organization",
    "project.area": "text",
    "contract.amount_reference": "money",
    "project.start_date": "date",
    "project.completion_date": "date",
    "acceptance.date": "date",
    "acceptance.conclusion": "text",
    "acceptance.signatures": "clauses",
}

_FINAL_DETERMINATION_FIELDS = {
    "project.name": "text",
    "project.code": "text",
    "party.owner": "organization",
    "party.contractor": "organization",
    "audit.type": "text",
    "contract.amount_reference": "money",
    "audit.submitted_amount": "money",
    "audit.first_determined_amount": "money",
    "audit.second_determined_amount": "money",
    "audit.review_fee_deduction": "money",
    "audit.engineering_determined_amount": "money",
    "audit.final_settlement_amount": "money",
    "audit.reduction_amount": "money",
    "audit.reduction_rate": "percentage",
    "audit.determination_date": "date",
    "audit.uppercase_amount": "money_uppercase",
}


SCHEMAS = {
    "contract.v1": ExtractionSchema(
        "contract.v1", "construction_contract", _CONTRACT_FIELDS
    ),
    "acceptance.v1": ExtractionSchema(
        "acceptance.v1",
        "completion_acceptance_certificate",
        _ACCEPTANCE_FIELDS,
    ),
    "final_determination.v1": ExtractionSchema(
        "final_determination.v1",
        "final_audit_determination",
        _FINAL_DETERMINATION_FIELDS,
    ),
}

SCHEMA_VERSION_BY_DOCUMENT_TYPE = {
    schema.document_type: version for version, schema in SCHEMAS.items()
}


def schema_for_version(version):
    try:
        return SCHEMAS[str(version)]
    except KeyError:
        raise ValueError(f"unsupported extraction schema: {version}") from None


def schema_for_document_type(document_type):
    version = SCHEMA_VERSION_BY_DOCUMENT_TYPE.get(str(document_type))
    if not version:
        raise ValueError(f"unsupported document type: {document_type}")
    return SCHEMAS[version]
