"""
seed_colombia_entities.py — Seeding script for Colombia Tactical Surveillance Entities.
Populates the entity registry with armed groups, key leaders, political figures,
analysts, critical infrastructure, and geographic surveillance nodes.
Run: python seed_colombia_entities.py
"""
import logging
import sys
from pathlib import Path

from entity_registry import get_stats, register

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

COLOMBIA_ENTITIES = [
    # ── Grupos Armados e Irregulares ──
    {
        "canonical_name": "ELN",
        "entity_type": "armed_group",
        "aliases": ["Ejército de Liberación Nacional", "ELN Colombia", "Frente de Guerra ELN"],
        "properties": {"country": "Colombia", "status": "active", "category": "guerrilla"},
    },
    {
        "canonical_name": "Estado Mayor Central",
        "entity_type": "armed_group",
        "aliases": ["EMC", "EMC-FARC", "Disidencias FARC EMC", "Estado Mayor Central FARC"],
        "properties": {"country": "Colombia", "status": "active", "category": "dissidents"},
    },
    {
        "canonical_name": "Segunda Marquetalia",
        "entity_type": "armed_group",
        "aliases": ["Segunda Marquetalia FARC", "Marquetalios", "Disidencias Segunda Marquetalia"],
        "properties": {"country": "Colombia", "status": "active", "category": "dissidents"},
    },
    {
        "canonical_name": "Clan del Golfo",
        "entity_type": "armed_group",
        "aliases": ["AGC", "Autodefensas Gaitanistas de Colombia", "Los Urabeños", "EGC", "Ejército Gaitanista"],
        "properties": {"country": "Colombia", "status": "active", "category": "cartel_narco"},
    },
    {
        "canonical_name": "Comandos de la Frontera",
        "entity_type": "armed_group",
        "aliases": ["CDF", "Comandos de Frontera Putumayo"],
        "properties": {"country": "Colombia", "status": "active", "region": "Putumayo"},
    },
    {
        "canonical_name": "Los Pachencas",
        "entity_type": "armed_group",
        "aliases": ["Autodefensas Conquistadoras de la Sierra Nevada", "ACSN"],
        "properties": {"country": "Colombia", "status": "active", "region": "Sierra Nevada"},
    },
    {
        "canonical_name": "Frente Carlos Patiño",
        "entity_type": "armed_group_front",
        "aliases": ["Frente Carlos Patiño EMC", "Carlos Patiño Cauca"],
        "properties": {"country": "Colombia", "parent_group": "EMC", "region": "Cauca"},
    },
    {
        "canonical_name": "Frente 33",
        "entity_type": "armed_group_front",
        "aliases": ["Frente 33 Catatumbo", "Frente 33 EMC"],
        "properties": {"country": "Colombia", "parent_group": "EMC", "region": "Catatumbo"},
    },
    {
        "canonical_name": "Frente Adán Izquierdo",
        "entity_type": "armed_group_front",
        "aliases": ["Frente Adán Izquierdo EMC"],
        "properties": {"country": "Colombia", "parent_group": "EMC", "region": "Valle/Cauca"},
    },

    # ── Comandantes / Líderes Irregulares ──
    {
        "canonical_name": "Calarcá",
        "entity_type": "person_commander",
        "aliases": ["Alexander Díaz Mendoza", "Calarcá Córdoba", "Líder Estado Mayor Central"],
        "properties": {"group": "EMC", "role": "commander"},
    },
    {
        "canonical_name": "Antonio García",
        "entity_type": "person_commander",
        "aliases": ["Eliécer Herlinto Chamorro Acosta", "Comandante ELN"],
        "properties": {"group": "ELN", "role": "supreme_commander"},
    },
    {
        "canonical_name": "Iván Márquez",
        "entity_type": "person_commander",
        "aliases": ["Luciano Marín Arango", "Jefe Segunda Marquetalia"],
        "properties": {"group": "Segunda Marquetalia", "role": "commander"},
    },
    {
        "canonical_name": "Chiquito Malo",
        "entity_type": "person_commander",
        "aliases": ["Jobanis de Jesús Ávila Villadiego", "Líder Clan del Golfo"],
        "properties": {"group": "Clan del Golfo", "role": "supreme_commander"},
    },

    # ── Figuras Políticas y Gobierno ──
    {
        "canonical_name": "Abelardo de la Espriella",
        "entity_type": "person_politician",
        "aliases": ["ADLE", "Abelardo de la Espriella Morales"],
        "properties": {"country": "Colombia", "role": "candidate_political_figure"},
    },
    {
        "canonical_name": "Gustavo Petro",
        "entity_type": "person_politician",
        "aliases": ["Presidente Petro", "Gustavo Petro Urrego"],
        "properties": {"country": "Colombia", "role": "president"},
    },
    {
        "canonical_name": "Iván Cepeda",
        "entity_type": "person_politician",
        "aliases": ["Senador Iván Cepeda", "Iván Cepeda Castro"],
        "properties": {"country": "Colombia", "role": "senator"},
    },
    {
        "canonical_name": "José Manuel Restrepo",
        "entity_type": "person_politician",
        "aliases": ["Vicepresidente Restrepo", "José Manuel Restrepo Abondano"],
        "properties": {"country": "Colombia", "role": "vice_president"},
    },
    {
        "canonical_name": "Honorio Miguel Henríquez",
        "entity_type": "person_politician",
        "aliases": ["Presidente del Congreso Henríquez", "Honorio Henríquez Pinedo"],
        "properties": {"country": "Colombia", "role": "congress_president"},
    },

    # ── Instituciones / Fuerza Pública ──
    {
        "canonical_name": "Presidencia de la República (Colombia)",
        "entity_type": "organization_government",
        "aliases": ["Casa de Nariño", "Presidencia Colombia"],
        "properties": {"country": "Colombia"},
    },
    {
        "canonical_name": "Ministerio de Defensa Colombia",
        "entity_type": "organization_government",
        "aliases": ["Mindefensa Colombia", "Ministerio de Defensa"],
        "properties": {"country": "Colombia"},
    },
    {
        "canonical_name": "Fuerzas Militares de Colombia",
        "entity_type": "organization_military",
        "aliases": ["FFMM Colombia", "Ejército Nacional de Colombia", "Fuerza Aérea Colombiana", "Armada Nacional de Colombia", "Gaula"],
        "properties": {"country": "Colombia"},
    },
    {
        "canonical_name": "JEP",
        "entity_type": "organization_judiciary",
        "aliases": ["Jurisdicción Especial para la Paz", "JEP Colombia"],
        "properties": {"country": "Colombia", "category": "transitional_justice"},
    },

    # ── Analistas y Voces de Referencia ──
    {
        "canonical_name": "Ariel Ávila",
        "entity_type": "person_analyst",
        "aliases": ["@ArielAvilaAnaliza", "Senador Ariel Ávila"],
        "properties": {"twitter": "@ArielAvilaAnaliza", "affiliation": "Senado / Ex-Pares"},
    },
    {
        "canonical_name": "León Valencia",
        "entity_type": "person_analyst",
        "aliases": ["@LeonVaLenciaA", "Director Pares"],
        "properties": {"twitter": "@LeonVaLenciaA", "affiliation": "Fundación Pares"},
    },
    {
        "canonical_name": "María Victoria Llorente",
        "entity_type": "person_analyst",
        "aliases": ["@FIP_Col", "Directora FIP"],
        "properties": {"twitter": "@FIP_Col", "affiliation": "FIP"},
    },
    {
        "canonical_name": "Camilo González Posso",
        "entity_type": "person_analyst",
        "aliases": ["@Indepaz", "Presidente Indepaz"],
        "properties": {"twitter": "@Indepaz", "affiliation": "Indepaz"},
    },
    {
        "canonical_name": "Daniel Mejía Londoño",
        "entity_type": "person_analyst",
        "aliases": ["@DanielMejiaL"],
        "properties": {"twitter": "@DanielMejiaL", "affiliation": "UniAndes"},
    },

    # ── Infraestructura Crítica y Sectores ──
    {
        "canonical_name": "Oleoducto Caño Limón-Coveñas",
        "entity_type": "infrastructure_pipeline",
        "aliases": ["Caño Limón", "Oleoducto Caño Limón"],
        "properties": {"sector": "oil_energy", "country": "Colombia"},
    },
    {
        "canonical_name": "Ecopetrol",
        "entity_type": "organization_company",
        "aliases": ["Ecopetrol S.A."],
        "properties": {"sector": "oil_energy", "country": "Colombia"},
    },
]


def seed_entities():
    logger.info("[COLOMBIA SEED] Seeding Colombia tactical entities...")
    count = 0
    for ent in COLOMBIA_ENTITIES:
        try:
            eid = register(
                canonical_name=ent["canonical_name"],
                entity_type=ent["entity_type"],
                source="colombia_surveillance_v1",
                aliases=ent.get("aliases", []),
                properties=ent.get("properties", {}),
            )
            count += 1
            logger.info(f"  + Registered: {ent['canonical_name']} ({eid})")
        except Exception as e:
            logger.error(f"  ! Error registering {ent['canonical_name']}: {e}")

    stats = get_stats()
    logger.info(f"[COLOMBIA SEED] Registered {count} Colombia tactical entities.")
    logger.info(f"[COLOMBIA SEED] Total Registry Entities: {stats.get('total_entities')}")
    return count


if __name__ == "__main__":
    seed_entities()
