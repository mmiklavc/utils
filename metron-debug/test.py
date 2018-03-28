#!/usr/bin/python

import sys

class Test:

    def __init__(self):
        print("inited")

    def doAll(self):
        print("doing all!")
        self.doA('calling doA')
        self.doB('calling doB')
        self.doC('calling doC')

    def doA(self, aval):
        self.vala = aval
        print(self.vala)

    def doB(self, bval):
        self.valb = bval
        print(self.valb)

    def doC(self, cval):
        print(cval)
        self.doA('ac')
        self.doB('bc')

if __name__ == "__main__":
    Test().doAll()

