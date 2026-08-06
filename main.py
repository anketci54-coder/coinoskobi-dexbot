from app.core.logger import logger
from app.config.settings import APP_NAME
from app.chains.bsc import connect, chain_id, latest_block
from app.wallet.account import wallet_address, bnb_balance

logger.info(APP_NAME)

if not connect():
    logger.error("RPC bağlantısı kurulamadı.")
    raise SystemExit(1)

logger.success("RPC bağlantısı başarılı.")
logger.info(f"Chain ID      : {chain_id()}")
logger.info(f"Latest Block  : {latest_block()}")

address = wallet_address()

if address:
    logger.success(f"Wallet        : {address}")
    logger.success(f"BNB Balance   : {bnb_balance()} BNB")
else:
    logger.warning("PRIVATE_KEY bulunamadı. Wallet modülü pasif.")
