from pathlib import Path


SOURCE_POLICIES = {
    "Clinical Guidance": {
        "category": "clinical_guidance",
        "authority_tier": "A",
        "included": True,
        "eligible_as_final_evidence": True,
        "reason": "A 级核心证据",
    },
    "Expert Consensus": {
        "category": "expert_consensus",
        "authority_tier": "A",
        "included": True,
        "eligible_as_final_evidence": True,
        "reason": "A 级核心证据",
    },
    "Textbook": {
        "category": "textbook",
        "authority_tier": "B",
        "included": True,
        "eligible_as_final_evidence": True,
        "reason": "B 级补充证据",
    },
    "Web Article": {
        "category": "web_article",
        "authority_tier": "C",
        "included": False,
        "eligible_as_final_evidence": False,
        "reason": "首版排除：规模过大且来源权威性未核验",
    },
    "Wiki": {
        "category": "wiki",
        "authority_tier": "C",
        "included": False,
        "eligible_as_final_evidence": False,
        "reason": "首版排除：词条边界和医学主题尚未重建",
    },
    "EMR": {
        "category": "emr",
        "authority_tier": "excluded",
        "included": False,
        "eligible_as_final_evidence": False,
        "reason": "首版排除：病历不是规范性证据，且需隐私审计",
    },
}

PARSER_VERSION = "source_parser_v1"
INDEX_VERSION = "corpus_v1"


def policy_for_path(path: Path, corpus_root: Path):
    relative = path.relative_to(corpus_root)
    return SOURCE_POLICIES.get(relative.parts[0])

