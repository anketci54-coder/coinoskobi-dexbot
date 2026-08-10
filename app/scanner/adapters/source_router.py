from app.config.registry import get_source
from app.scanner.adapters.registry import normalize


def normalize_source_rows(
    source_name,
    rows,
):
    source = get_source(source_name)

    if not source["enabled"]:
        raise RuntimeError(
            f"source disabled: {source_name}"
        )

    adapter_name = source["adapter"]

    candidates = []
    rejected = 0

    for row in rows:
        try:
            candidates.append(
                normalize(
                    adapter_name,
                    row,
                )
            )
        except (
            TypeError,
            ValueError,
            KeyError,
        ):
            rejected += 1

    return {
        "candidates": candidates,
        "rejected": rejected,
        "source": source["name"],
        "adapter": adapter_name,
    }
