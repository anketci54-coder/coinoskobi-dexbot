NETWORKS = {
    "bsc": {
        "chain_id": 56,
        "enabled": True,
        "rpc_key": "bsc",
    },

    # Gelecekte adapter/config ile aktive edilir.
    # Pipeline kopyalanmaz.
    "ethereum": {
        "chain_id": 1,
        "enabled": False,
        "rpc_key": "ethereum",
    },

    "base": {
        "chain_id": 8453,
        "enabled": False,
        "rpc_key": "base",
    },
}


DEXES = {
    "pancakeswap_v2": {
        "enabled": True,
        "chains": {"bsc"},
    },

    "pancakeswap_v3": {
        "enabled": True,
        "chains": {"bsc"},
    },

    "four-meme": {
        "enabled": True,
        "chains": {"bsc"},
    },

    # Gecko live sonuçlarında görülebiliyor.
    # Ingress ALLOWED_DEX ayrı policy katmanıdır.
    "uniswap-v4-bsc": {
        "enabled": True,
        "chains": {"bsc"},
    },

    # Gelecek örnekleri.
    "uniswap_v3": {
        "enabled": False,
        "chains": {"ethereum", "base"},
    },
}


SOURCES = {
    "geckoterminal": {
        "enabled": True,
        "networks": {
            "bsc": {
                "adapter": "gecko_bsc",
            },
        },
    },
}


def get_network(name):
    key = str(name).strip().lower()

    network = NETWORKS.get(key)

    if network is None:
        raise KeyError(
            f"unknown network: {key}"
        )

    return {
        "name": key,
        **network,
    }


def get_dex(name):
    key = str(name).strip().lower()

    dex = DEXES.get(key)

    if dex is None:
        raise KeyError(
            f"unknown dex: {key}"
        )

    return {
        "name": key,
        **dex,
    }


def get_source(name):
    key = str(name).strip().lower()

    source = SOURCES.get(key)

    if source is None:
        raise KeyError(
            f"unknown source: {key}"
        )

    return {
        "name": key,
        **source,
    }


def get_source_network(
    source_name,
    network_name,
):
    source = get_source(source_name)
    network = get_network(network_name)

    if not source["enabled"]:
        raise RuntimeError(
            f"source disabled: {source_name}"
        )

    if not network["enabled"]:
        raise RuntimeError(
            f"network disabled: {network_name}"
        )

    binding = source["networks"].get(
        network["name"]
    )

    if binding is None:
        raise KeyError(
            f"source {source_name} does not support "
            f"network {network_name}"
        )

    return {
        "source": source["name"],
        "network": network["name"],
        "chain_id": network["chain_id"],
        **binding,
    }


def enabled_networks():
    return [
        name
        for name, config in NETWORKS.items()
        if config["enabled"]
    ]


def enabled_dexes(chain=None):
    result = []

    for name, config in DEXES.items():

        if not config["enabled"]:
            continue

        if chain is not None:
            normalized_chain = (
                str(chain).strip().lower()
            )

            if normalized_chain not in config["chains"]:
                continue

        result.append(name)

    return result


def dex_supports_chain(
    dex_name,
    chain,
):
    dex = get_dex(dex_name)

    normalized_chain = (
        str(chain).strip().lower()
    )

    return normalized_chain in dex["chains"]
