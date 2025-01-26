
class UnnameClass:
    name = "UnnameClass"
    def __getitem__(self, key):
        return self.__dict__.get(key)
    def __setitem__(self, key, val):
        self.__dict__[key] = val
        return self
    def __str__(self):
        return "<"+self.name+"\n   "+"\n   ".join(["{: <15} : {}".format(i, str(self.__dict__.get(i))) for i in self.__dict__])+"\n>"
    def __repr__(self):
        return self.__str__()
    
class Structure:
    def __init__(self, *option, **kvoption):
        self.options = option
        self.kvoptions = kvoption
    def isContentOption(self, opt):
        if opt in self.kvoptions.keys():
            return True
        return False
    def isOption(self, opt):
        return not self.isContentOption(opt)
    def getContentCount(self, opt):
        return self.kvoptions.get(opt, 0)

    
"""test.py -test [content] -test2 [content] -t -ttt [content3]"""
"""test.py -test [content]"""

def getArrContent(i, arr):
    if len(arr) > i and i >= 0:
        return arr[i]
    return None

class decoder:
    def __init__(self, argv, structure=None):
        structure = structure if structure else Structure()
        argv      = argv[1:]

        valStructure = UnnameClass()
        valStructure.finalContent = []
        
        skipNextCont = False
        nowKey = None

        for i in range(len(argv)):
            prevCont = getArrContent(i-1, argv)
            nextCont = getArrContent(i+1, argv)
            cont     = argv[i]

            if skipNextCont:
                if not cont[0] == '-':
                    skipNextCont -= 1
                    valStructure[nowKey].append(cont)
                    continue
                else:
                    skipNextCont = 0

            if len(cont) >= 2 and cont[0] == '-':
                if structure.isOption(cont[1:]):
                    valStructure[cont] = True
                else:
                    nowKey = cont
                    valStructure[cont] = []
                    if structure.getContentCount(cont[1:]) == 1:
                        skipNextCont = 1
                    else:
                        skipNextCont += structure.getContentCount(cont[1:])
                continue

            valStructure.finalContent.append(cont)
            
        self.values = valStructure

def decode(arr, structure=None):
    return decoder(arr, structure).values



if __name__ == "__main__":
    stru = Structure(second=2)
    print(decode(["test.py", "-second", "WC", "Ssss", 'wcc', "That's the final content"], stru))
