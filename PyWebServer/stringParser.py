
import re, traceback
import server_config as sc
"""
{{Key}}

{{test()}}
"""
import Logger


Logger = Logger.Logger()


def getServerArg():
    x = dict(sc.setting, **sc.config)
    x['headers'] = sc.opts.get("headers")
    return x


def ParseString(String, vars):
    vars = dict(vars, **getServerArg())
    for k in vars:
        val = vars[k]
        String = String.replace("{{"+k+"}}", str(val))
    
    keys = re.findall(r"\{\{(.*?)\}\}", String)

    for i in keys:
        try:
            r = eval(i, vars)
            String = String.replace("{{"+i+"}}", str(r))
        except Exception as e:
            print("Inconsistent expression:", i)
            print("      "+traceback.format_exc().replace("\n", "\n      "))
    return String

if __name__ == '__main__':
    print(
    ParseString("""{{1+2+3+4+5}}|{{ip}}""", globals())
    )
