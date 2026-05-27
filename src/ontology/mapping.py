from collections.abc import Mapping

from rdflib import RDF, Graph, Literal, Namespace

from src.schemas.extraction import ComparableField, ExtractionResult


DNB = Namespace("https://dnb-harness.local/ontology#")
DATA = Namespace("https://dnb-harness.local/data#")


def extraction_to_graph(extraction: ExtractionResult) -> Graph:
    graph = Graph()
    graph.bind("dnb", DNB)
    graph.bind("data", DATA)

    _add_document_structure(graph, "contract")
    _add_document_structure(graph, "im")

    _add_fields(
        graph,
        DATA.fund_contract,
        {
            "fund_name": extraction.fund.name,
            "fund_type": extraction.fund.type,
            "inception_date": extraction.fund.inception_date,
            "maturity_date": extraction.fund.maturity_date,
        },
        "contract",
    )
    _add_fields(
        graph,
        DATA.fund_im,
        {
            "fund_name": extraction.fund.name,
            "fund_type": extraction.fund.type,
            "inception_date": extraction.fund.inception_date,
            "maturity_date": extraction.fund.maturity_date,
        },
        "im",
    )

    _add_fields(
        graph,
        DATA.party_contract,
        {
            "asset_manager": extraction.party.asset_manager,
            "trustee": extraction.party.trustee,
            "distributor": extraction.party.distributor,
        },
        "contract",
    )
    _add_fields(
        graph,
        DATA.party_im,
        {
            "asset_manager": extraction.party.asset_manager,
            "trustee": extraction.party.trustee,
            "distributor": extraction.party.distributor,
        },
        "im",
    )

    _add_fields(
        graph,
        DATA.fee_schedule_contract,
        {
            "management_fee": extraction.fee_schedule.management_fee,
            "trust_fee": extraction.fee_schedule.trust_fee,
            "sales_fee": extraction.fee_schedule.sales_fee,
        },
        "contract",
    )
    _add_fields(
        graph,
        DATA.fee_schedule_im,
        {
            "management_fee": extraction.fee_schedule.management_fee,
            "trust_fee": extraction.fee_schedule.trust_fee,
            "sales_fee": extraction.fee_schedule.sales_fee,
        },
        "im",
    )

    _add_fields(
        graph,
        DATA.redemption_terms_contract,
        {
            "is_redeemable": extraction.redemption_terms.is_redeemable,
            "lockup_period": extraction.redemption_terms.lockup_period,
            "redemption_cycle": extraction.redemption_terms.redemption_cycle,
            "redemption_fee": extraction.redemption_terms.redemption_fee,
        },
        "contract",
    )
    _add_fields(
        graph,
        DATA.redemption_terms_im,
        {
            "is_redeemable": extraction.redemption_terms.is_redeemable,
            "lockup_period": extraction.redemption_terms.lockup_period,
            "redemption_cycle": extraction.redemption_terms.redemption_cycle,
            "redemption_fee": extraction.redemption_terms.redemption_fee,
        },
        "im",
    )

    return graph


def _add_document_structure(graph: Graph, document_scope: str) -> None:
    fund = DATA[f"fund_{document_scope}"]
    party = DATA[f"party_{document_scope}"]
    fee_schedule = DATA[f"fee_schedule_{document_scope}"]
    redemption_terms = DATA[f"redemption_terms_{document_scope}"]

    graph.add((fund, RDF.type, DNB.Fund))
    graph.add((party, RDF.type, DNB.Party))
    graph.add((fee_schedule, RDF.type, DNB.FeeSchedule))
    graph.add((redemption_terms, RDF.type, DNB.RedemptionTerms))

    graph.add((fund, DNB.has_party, party))
    graph.add((fund, DNB.has_fee_schedule, fee_schedule))
    graph.add((fund, DNB.has_redemption_terms, redemption_terms))


def _add_fields(
    graph: Graph,
    subject,
    fields: Mapping[str, ComparableField],
    document_scope: str,
) -> None:
    for property_name, field in fields.items():
        document_value = getattr(field, document_scope)
        if document_value.raw_text is None:
            continue
        graph.add((subject, DNB[property_name], Literal(document_value.raw_text)))
