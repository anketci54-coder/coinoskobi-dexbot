from app.pipeline.normalizer import CandidateNormalizer





def _mocknet_test(row):
    from app.pipeline.candidate import Candidate

    return Candidate.from_row(
        row,
        chain="mocknet",
        chain_id=999999,
        source="geckoterminal",
    )


ADAPTERS = {
    "gecko_bsc": CandidateNormalizer.gecko_bsc,
    "mocknet_test": _mocknet_test,
}


def get_adapter(name):
    key = str(name).strip().lower()

    adapter = ADAPTERS.get(key)

    if adapter is None:
        raise KeyError(
            f"unknown source adapter: {key}"
        )

    return adapter


def normalize(
    adapter_name,
    row,
):
    adapter = get_adapter(
        adapter_name
    )

    return adapter(row)
