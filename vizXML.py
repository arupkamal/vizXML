import xml.etree.ElementTree as ET
import sqldf
import pandas as pd
from graphviz import Digraph
import math

class vizXML:
    def __init__(self, xmlFile, diaName):
        self.edges = []
        self.nodes = []
        self.dot   = None
        self.tree = ET.parse(xmlFile)
        self.root = self.tree.getroot()
        self.diaName = diaName
        self.run()
        self.df = None
        
    def cx(self,n):
        return math.log(n,50)

    def walk(self, node, parNode):
        nChild = len(node)
        if nChild>0:
            for childNode in node:
                nodeName = parNode.tag +'.'+ node.tag

                if len(childNode)<1:
                    childNodeName = node.tag+"."+childNode.tag
                else:
                    childNodeName = node.tag+"."+childNode.tag
                self.edges.append({"src":nodeName, "dst": childNodeName})
                self.walk(childNode, node)
        else:
            nodeName = node.tag+"*"    
            
    def run(self):
        self.walk(self.root, self.root)

        global mySpecialDataFrame7132
        mySpecialDataFrame7132 = pd.DataFrame(self.edges)
        mySpecialDataFrame7132 = sqldf.run("select src, dst, count(*) [wgt] from mySpecialDataFrame7132 group by src, dst")
        self.edges = mySpecialDataFrame7132 [['src','dst', 'wgt']]
        self.nodes = list(set(self.edges.src.to_list()+self.edges.dst.to_list()))

        self.dot = Digraph(comment = self.diaName)

        for node in self.nodes:
            self.dot.attr('node', shape='box', style='rounded')
            self.dot.node(node, node.split('.')[1],fontname='Imago', fontsize='10')

        for index, row in df.iterrows():
            self.dot.edge(row['src'], row['dst'], arrowsize="0.6", penwidth="0.7", color= f"0.6 {0.3+self.cx(row['wgt'])/1.1} 0.878", arrowtype='open')

        self.dot.attr(rankdir='TB')
        self.dot.graph_attr['layout']= 'dot'
        self.dot.render(f'{self.diaName}.gv', view=True) 
        
# vizXML(r'sample.xml', 'sample.xml')
