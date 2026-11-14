import unittest
from bs4 import BeautifulSoup
from monitor.portais import ifpb,ifsertaope
from monitor.common import format_message
class Tests(unittest.TestCase):
 def test_ifpb_table(self):
  soup=BeautifulSoup('<table class="edital-items-table"><tbody class="edital-items-body"><tr class="edital-item-row"><td class="title"><a href="/doc.pdf">Resultado</a></td><td class="description">Resultado preliminar</td><td class="date"><time datetime="2026-11-11T17:24">11/11/2026, 17:24</time></td></tr></tbody></table>','html.parser')
  d=ifpb.extract(soup,'https://www.ifpb.edu.br/edital-n-1','Edital 1');self.assertEqual(len(d),1);self.assertIn('11/11/2026',next(iter(d.values()))['date'])
 def test_ifsertaope_table(self):
  soup=BeautifulSoup('<table class="edital__table"><tbody><tr><td>28/09/2026 10:26</td><td><a href="/wp-content/uploads/a.pdf">Resultado final</a></td><td>Publicações</td></tr></tbody></table>','html.parser')
  d=ifsertaope.extract(soup,'https://ifsertaope.edu.br/editais/edital-n-o-118-2026/','Edital 118');self.assertEqual(len(d),1)
 def test_signature(self):
  item=dict(portal='IFPB',kind='Resultado',edital='Edital 161',doc='Resultado',date='11/11/2026',link='https://ifpb.edu.br/a',origin='https://ifpb.edu.br/')
  self.assertIn('Desenvolvido por Diego Tech',format_message(item,True))
if __name__=='__main__':unittest.main()
