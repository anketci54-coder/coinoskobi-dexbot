class CandidateFilter:

    MIN_CODE_SIZE = 1000

    def accept(self, token_info, pair_info, risk_info):

        reasons = []

        if not token_info.get("name"):
            reasons.append("ERC20 okunamadı")

        if not pair_info.get("exists", False):
            reasons.append("Pair yok")

        if risk_info.get("code_size", 0) < self.MIN_CODE_SIZE:
            reasons.append("Bytecode küçük")

        if reasons:
            return {
                "accepted": False,
                "reasons": reasons
            }

        return {
            "accepted": True,
            "reasons": ["Filtreyi geçti"]
        }
