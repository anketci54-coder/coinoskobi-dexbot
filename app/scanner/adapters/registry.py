from app.pipeline.normalizer import CandidateNormalizer


ADAPTERS = {
    "gecko_bsc": CandidateNormalizer.gecko_bsc,
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
