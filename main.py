from app.core.logger import logger
from app.config.settings import APP_NAME
from app.chains.bsc import connect, chain_id, latest_block

logger.info(APP_NAME)

if not connect():
    logger.error("RPC bağlantısı kurulamadı.")
    raise SystemExit(1)

logger.success("RPC bağlantısı başarılı.")
logger.info(f"Chain ID : {chain_id()}")
logger.info(f"Latest Block : {latest_block()}")
