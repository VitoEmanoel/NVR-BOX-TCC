import sys
sys.path.insert(0, sys.argv[1])
from nvrbox import config
config._candidatos_armazenamento_externo = lambda: iter(())
from nvrbox import servidor
servidor.app.run(host="127.0.0.1", port=5000, threaded=True)
