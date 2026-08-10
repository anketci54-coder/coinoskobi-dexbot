from app.config.registry import get_source_network
from app.scanner.adapters.registry import normalize


def normalize_source_rows(
    source_name,
    network_name,
    rows,
):
    binding = get_source_network(
        source_name,
        network_name,
    )

    adapter_name = binding["adapter"]

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
        "source": binding["source"],
        "network": binding["network"],
        "chain_id": binding["chain_id"],
        "adapter": adapter_name,
    }
