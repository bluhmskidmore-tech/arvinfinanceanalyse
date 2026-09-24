from backend.app.ontology.loader import OntologyIndex, load_ontology_index
from backend.app.ontology.models import OntologyDocument, OntologyEntity, OntologyRelationship

__all__ = [
    "OntologyDocument",
    "OntologyEntity",
    "OntologyIndex",
    "OntologyRelationship",
    "load_ontology_index",
]
