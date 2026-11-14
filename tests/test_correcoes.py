import unittest
from bs4 import BeautifulSoup
from monitor.portais import compec
class TestCorrecoes(unittest.TestCase):
 def test_uuid_sem_ano(self):
  url='https://concursos.ifpb.edu.br/processos_seletivos/concurso/beab9b5a-0554-4ee8-8f8e-6e959520deb9/'
  soup=BeautifulSoup('<a href="'+url+'">Ver detalhes</a>','html.parser')
  self.assertEqual(len(compec.processes(soup,compec.ROOT)),1)
 def test_documento_oficial(self):
  origin='https://concursos.ifpb.edu.br/processos_seletivos/concurso/beab9b5a-0554-4ee8-8f8e-6e959520deb9/'
  soup=BeautifulSoup('<main><a href="https://estudante.ifpb.edu.br/arquivo/resultado.pdf">Resultado final</a><a href="/login">Entrar</a></main>','html.parser')
  docs=compec.extract(soup,origin+'documentos/',origin,'Edital 143/2026')
  self.assertEqual(len(docs),1)
if __name__=='__main__':unittest.main()
