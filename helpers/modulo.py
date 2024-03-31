import urllib
import ftplib
import math
import io
import os
import gzip
import json
import pandas as pd
import matplotlib.pyplot as plt
from IPython.display import Image
from PIL import Image
from IPython.display import display
from datetime import datetime, timezone, timedelta
from shapely.geometry import Polygon
from google.colab import files

class QuadroSatelite:
    def __init__(self, indice_lat, indice_lon, poligono, imagem=None):
        self.indice_lat = indice_lat
        self.indice_lon = indice_lon
        self.poligono = poligono
        self.imagem = imagem

        if imagem is None:
            self.carregado = False
        else:
            self.carregado = True

    def carregarImagem(self, imagem):
        self.imagem = imagem
        self.carregado = True
        return True

    def nome_do_arquivo(self):
        # Define os prefixos com base nos sinais de latitude e longitude
        pre_lat = "S" if self.indice_lat < 0 else "N"
        pre_lon = "O" if self.indice_lon < 0 else "L"

        # Converte os Ã­ndices para hexadecimal e preenche com zeros Ã  esquerda para ter 8 dÃ­gitos
        lat_hex = format(abs(self.indice_lat), '08x')
        lon_hex = format(abs(self.indice_lon), '08x')

        # Retorna a string concatenada
        return f"{pre_lat}{lat_hex}{pre_lon}{lon_hex}"

class MascaraCategorica:
    def __init__(self, nome, categorias=None, imagem=None, quadros=None):
        self.nome = nome
        self.categorias = categorias
        self.imagem = imagem
        if quadros is None:
          self.quadros = pd.DataFrame(columns=['indice_lat','indice_lon','objeto','carregado','salvo'])
        else:
          self.quadros = quadros

    def gerar_quadro_pelos_indices(self, indice_lat, indice_lon):
        indices = [ indice_lat, indice_lon ]
        result = self.quadros[(self.quadros['indice_lat'] == indices[0]) & (self.quadros['indice_lon'] == indices[1])]

        if result.empty:
            poligono = self.imagem.poligono_do_quadro( indices[0], indices[1] )
            quadro = QuadroSatelite( indices[0], indices[1], poligono )

            self.quadros = pd.concat([ self.quadros , pd.DataFrame([{ "indice_lat":indices[0], "indice_lon":indices[1], "objeto":quadro, "carregado":False, "salvo":False }]) ], ignore_index=True)

        return indices

    def uploadImagemMascara(self):
        # Solicitar o upload do arquivo
        uploaded = files.upload()
        nome_do_arquivo = next(iter(uploaded))
        mascara = Image.open(io.BytesIO(uploaded[nome_do_arquivo]))

        lat = int(nome_do_arquivo[1:9], 16)
        lon = int(nome_do_arquivo[10:18],16)
        if nome_do_arquivo[0]=='S':
          lat *= -1
        if nome_do_arquivo[9]=='O':
          lon *= -1

        print(f"Quadro -> lat: {lat} , lon: {lon}")
        quadro = self.quadros[(self.quadros['indice_lat']==lat)&(self.quadros['indice_lon']==lon)]
        if quadro.shape[0]==0:
          self.gerar_quadro_pelos_indices(lat,lon)
          quadro = self.quadros[(self.quadros['indice_lat']==lat)&(self.quadros['indice_lon']==lon)]
        quadro = quadro['objeto'].iloc[0]

        original = self.imagem.quadros[(self.imagem.quadros['indice_lat']==lat)&(self.imagem.quadros['indice_lon']==lon)]
        if original.shape[0]>0 and original['objeto'].iloc[0] is not None:
          original = original['objeto'].iloc[0]
          if original is not None:
            original = original.imagem
        else:
          original = None

        if original is None:
          display(mascara)
        else:
          display(original, mascara)

        lista = list(mascara.getdata())
        saida = []
        for pixel in lista:
          if pixel[3]<128:
            saida.append(0)
          else:
            mais_proximo = 0
            proximidade = 442
            for n, linha in self.categorias.iterrows():
              indice = linha['indice']
              cor = (int(linha['cor'][0:2],16), int(linha['cor'][2:4],16), int(linha['cor'][4:6],16))
              x = ((pixel[0]-cor[0])**2+(pixel[1]-cor[1])**2+(pixel[2]-cor[2])**2)**0.5
              if x < proximidade:
                mais_proximo = indice
                proximidade = x
            saida.append(mais_proximo)

        if(quadro.carregarImagem(saida)):
          self.quadros.loc[(self.quadros['indice_lat'] == lat) & (self.quadros['indice_lon'] == lon), 'carregado'] = True

class ImagemSatelite:
    RAIO_TERRA = 6.3781e6 # em metros
    PERIM_TERRA = 2*math.pi*RAIO_TERRA
    quadros = pd.DataFrame(columns=['indice_lat', 'indice_lon', 'objeto', 'carregado', 'salvo'])

    def __init__(self, projeto, mapa_id, geometria=None, dados=None, mascaras=None, bands=['B4', 'B3', 'B2'], ranges=[{'min': 1500, 'max': 3000}], quadro=[400,400]):
        self.projeto = projeto
        self.mapa_id = mapa_id
        self.bands = bands
        self.ranges = ranges
        self.geometria = geometria
        self.quadro = quadro
        if mascaras is None:
          self.mascaras = pd.DataFrame(columns=['nome','objeto','carregado','salvo'])
        else:
          self.mascaras = mascaras
        if dados is None:
            display("Escala: "+str(self.carregar_escala(projeto, mapa_id[0]))+" metros por pixel")
        else:
            self.data=dados['data']
            self.hora=dados['hora']
            self.escala=dados['escala']
            if 'bands' in dados:
              self.bands=dados['bands']
            if 'ranges' in dados:
              self.ranges=dados['ranges']
            if 'geometria' in dados:
              self.ranges=dados['geometria']

    def carregar_escala(self, projeto, mapa_id):
        global session

        # Construindo o nome do recurso com base no projeto, asset_id e map_id fornecido
        name = f'{projeto}/assets/{mapa_id}'

        # Definindo a URL para acessar os metadados da imagem especÃ­fica
        url = f'https://earthengine.googleapis.com/v1alpha/{name}'

        # Fazendo a requisiÃ§Ã£o para obter os metadados da imagem
        response = session.get(url)

        # Verificando se a requisiÃ§Ã£o foi bem-sucedida
        if response.status_code == 200:
            # Carregando o conteÃºdo da resposta
            content = json.loads(response.content)

            data = datetime.fromisoformat(content['endTime'].rstrip("Z")).replace(tzinfo=timezone.utc)
            self.data = data.strftime("%Y-%m-%d")
            self.hora = data.strftime("%H:%M:%S")

            # Extraindo a informaÃ§Ã£o de 'bands' dos metadados
            if 'bands' in content:
                bands = pd.DataFrame(content['bands'])

                # Procurando a banda especÃ­fica, por exemplo, 'B2'
                try:
                    # Encontrando a escala (metros por pixel) para a banda especificada
                    self.escala = [abs(bands[bands['id']=='B2']['grid'].iloc[0]['affineTransform']['scaleY']), abs(bands[bands['id']=='B2']['grid'].iloc[0]['affineTransform']['scaleX'])]
                    return self.escala
                except (KeyError, IndexError) as e:
                    print(f"Erro ao tentar acessar a escala da banda: {e}")
                    return None
            else:
                print("InformaÃ§Ãµes de bandas nÃ£o encontradas nos metadados.")
                return None
        else:
            print("Falha na requisiÃ§Ã£o: ", response.status_code)
            return None

    def definir_quadro(self, altura, largura): # definindo o tamanho de cada imagem do mapa
        self.quadro=[altura, largura]

    def indice_da_latitude(self, latitude): # encontrar o Ã­ndice da imagem pela latitude, sendo o equador=0
        return math.floor( latitude * self.PERIM_TERRA / 360 / self.escala[0] / self.quadro[0] )

    def latitude_media_do_indice(self, indice): # encontrar a latitude do centro do quadro
        return 360.0 * (indice+0.5) * self.escala[0] * self.quadro[0] / self.PERIM_TERRA

    def latitude_minima_do_indice(self, indice): # encontrar a latitude mÃ­nima do quadro
        return 360 * indice * self.escala[0] * self.quadro[0] / self.PERIM_TERRA

    def latitude_maxima_do_indice(self, indice): #encontrar a latitude mÃ¡xima do quadro
        return self.latitude_minima_do_indice(indice+1)

    def longitude_na_latitude(self, latitude): # retorna o tamanho da linha longitudinal em metros
        return 2 * math.pi * self.RAIO_TERRA * math.cos(math.radians(latitude))

    def indice_da_longitude(self, longitude, indice_lat): # calcular o Ã­ndice da imagem pela longitude, sendo greeenwich=0
        return math.floor( longitude * self.longitude_na_latitude(self.latitude_media_do_indice(indice_lat)) / 360 / self.escala[1] / self.quadro[1])

    def longitude_minima_do_indice(self, indice, longitude_metros):
        return 360 * indice * self.escala[1] * self.quadro[1] / longitude_metros

    def longitude_maxima_do_indice(self, indice, longitude_metros):
        return self.longitude_minima_do_indice(indice+1, longitude_metros)

    def indices_do_quadro(self, latitude, longitude): # calcular os Ã­ndices de um quadro dado as coordenadas
        indice_lat = self.indice_da_latitude(latitude)
        indice_lon = self.indice_da_longitude(longitude, indice_lat)
        return [indice_lat, indice_lon]

    def poligono_do_quadro(self, indice_lat, indice_lon):
        min_lat = self.latitude_minima_do_indice(indice_lat)
        max_lat = self.latitude_maxima_do_indice(indice_lat)
        longitude_metros = self.longitude_na_latitude(self.latitude_media_do_indice(indice_lat))
        min_lon = self.longitude_minima_do_indice(indice_lon, longitude_metros)
        max_lon = self.longitude_maxima_do_indice(indice_lon, longitude_metros)

        return {'type': 'Polygon',
              'coordinates': [[[min_lon, min_lat],
                              [max_lon, min_lat],
                              [max_lon, max_lat],
                              [min_lon, max_lat],
                              [min_lon, min_lat]]]}

    def area_do_poligono(self, poligono):
        min_lat = poligono["coordinates"][0][0][1]
        max_lat = poligono["coordinates"][0][0][1]
        min_lon = poligono["coordinates"][0][0][0]
        max_lon = poligono["coordinates"][0][0][0]
        for coord in poligono["coordinates"][0]:
          if coord[0]<min_lon:
            min_lon=coord[0]
          if coord[0]>max_lon:
            max_lon=coord[0]
          if coord[1]<min_lat:
            min_lat=coord[1]
          if coord[1]>max_lat:
            max_lat=coord[1]
        return [min_lat,max_lat,min_lon,max_lon]

    def gerar_quadro_pela_localizacao(self, latitude, longitude):
        indices = self.indices_do_quadro( latitude, longitude )
        result = self.quadros[(self.quadros['indice_lat'] == indices[0]) & (self.quadros['indice_lon'] == indices[1])]

        if result.empty:
            poligono = self.poligono_do_quadro( indices[0], indices[1] )
            quadro = QuadroSatelite( indices[0], indices[1], poligono )

            self.quadros = pd.concat([ self.quadros , pd.DataFrame([{ "indice_lat":indices[0], "indice_lon":indices[1], "objeto":quadro, "carregado":False, "salvo":False }]) ], ignore_index=True)

        return indices

    def gerar_quadro_pelos_indices(self, indice_lat, indice_lon):
        indices = [ indice_lat, indice_lon ]
        result = self.quadros[(self.quadros['indice_lat'] == indices[0]) & (self.quadros['indice_lon'] == indices[1])]

        if result.empty:
            poligono = self.poligono_do_quadro( indices[0], indices[1] )
            quadro = QuadroSatelite( indices[0], indices[1], poligono )

            self.quadros = pd.concat([ self.quadros , pd.DataFrame([{ "indice_lat":indices[0], "indice_lon":indices[1], "objeto":quadro, "carregado":False, "salvo":False }]) ], ignore_index=True)

        return indices

    def retornar_objeto_pelos_indices(self, indice_lat, indice_lon):
        result = self.quadros[(self.quadros['indice_lat'] == indice_lat) & (self.quadros['indice_lon'] == indice_lon)]

        if not result.empty:
            return result.iloc[0]['objeto']
        else:
            return None

    def carregar_quadro(self, indice_lat, indice_lon):
        global session

        objeto = self.retornar_objeto_pelos_indices( indice_lat, indice_lon )

        if objeto is None:
          return False

        if objeto.carregado==True:
          return True

        quadro = Polygon(self.poligono_do_quadro(indice_lat,indice_lon)['coordinates'][0])
        for indice, mapa_id in enumerate(self.mapa_id):
          mapa = Polygon(self.geometria[indice]['coordinates'][0])
          if mapa.contains(quadro):
            break;

        name = '{}/assets/{}'.format(self.projeto, mapa_id)

        url = 'https://earthengine.googleapis.com/v1alpha/{}:getPixels'.format(name)
        body = json.dumps({
            'fileFormat': 'PNG',
            'bandIds': self.bands,
            'region': objeto.poligono,
            'grid': {
                'dimensions': {'width': self.quadro[1], 'height': self.quadro[0]},    # Tamanho da imagem baixada
            },
            'visualizationOptions': {
                'ranges': self.ranges,
            },
        })

        image_response = session.post(url, body)
        image_content = image_response.content

        buffer = io.BytesIO(image_content)  # Cria um buffer com o conteÃºdo da imagem
        image = Image.open(buffer)  # Cria um objeto de imagem PIL a partir do buffer

        if objeto.carregarImagem(image):
            self.quadros.loc[(self.quadros['indice_lat'] == indice_lat) & (self.quadros['indice_lon'] == indice_lon), 'carregado'] = True
            return True
        else:
            return False

    def indices_da_area( self, min_lat, max_lat, min_lon, max_lon ):
        indices = []
        indice_lat_min = self.indice_da_latitude(min_lat)
        indice_lat_max = self.indice_da_latitude(max_lat)
        for indice_lat in range(indice_lat_min, indice_lat_max+1):
            indice_lon_min = self.indice_da_longitude(min_lon, indice_lat)
            indice_lon_max = self.indice_da_longitude(max_lon, indice_lat)
            for indice_lon in range(indice_lon_min, indice_lon_max+1):
                indices.append( [indice_lat, indice_lon] )
        return indices

    def area_em_pixeis( self, min_lat, max_lat, min_lon, max_lon ):
        lat_em_m = self.PERIM_TERRA*(max_lat-min_lat)/360
        lon_em_m = self.longitude_na_latitude((max_lat+min_lat)/2)*(max_lon-min_lon)/360

        return [round(lon_em_m/self.escala[0]), round(lat_em_m/self.escala[1])]

    def adiocionar_mascara(self, mascara):
        result = self.mascaras[(self.mascaras['nome'] == mascara.nome)]

        if result.empty:
            mascara.imagem = self
            self.mascaras = pd.concat([ self.mascaras , pd.DataFrame([{ "nome":mascara.nome, "objeto":mascara, "carregado":True}]) ], ignore_index=True)
            return mascara
        return None

    def nova_mascara(self, nome, categorias):
        result = self.mascaras[(self.mascaras['nome'] == nome)]

        if result.empty:
            mascara = MascaraCategorica( nome, categorias, imagem=self )
            self.mascaras = pd.concat([ self.mascaras , pd.DataFrame([{ "nome":nome, "objeto":mascara, "carregado":True}]) ], ignore_index=True)
            return mascara
        return None

    def preverMapa( self, min_lat, max_lat, min_lon, max_lon, max_tamanho=800):
        global session
        tam = self.area_em_pixeis(min_lat,max_lat,min_lon,max_lon)
        if tam[0]>tam[1]:
          if tam[0]>max_tamanho:
            tam[1]=round(max_tamanho*tam[1]/tam[0])
            tam[0]=max_tamanho
        else:
          if tam[1]>max_tamanho:
            tam[0]=round(max_tamanho*tam[0]/tam[1])
            tam[1]=max_tamanho

        imagem = Image.new("RGBA", (tam[0],tam[1]), (0,0,0,0))

        for mapa_id in self.mapa_id:
          name = '{}/assets/{}'.format(self.projeto, mapa_id)

          url = 'https://earthengine.googleapis.com/v1alpha/{}:getPixels'.format(name)
          body = json.dumps({
              'fileFormat': 'PNG',
              'bandIds': self.bands,
              'region': {'type': 'Polygon',
                'coordinates': [[[min_lon, min_lat],
                                [max_lon, min_lat],
                                [max_lon, max_lat],
                                [min_lon, max_lat],
                                [min_lon, min_lat]]]},
              'grid': {
                  'dimensions': {'width': tam[0], 'height': tam[1]},    # Tamanho da imagem baixada
              },
              'visualizationOptions': {
                  'ranges': self.ranges,
              },
          })

          image_response = session.post(url, body)
          image_content = image_response.content

          buffer = io.BytesIO(image_content)  # Cria um buffer com o conteÃºdo da imagem
          img = Image.open(buffer)  # Cria um objeto de imagem PIL a partir do buffer
          imagem.paste(img, (0,0), img)

        display(imagem)
        return imagem

    def visualizarMapa( self, min_lat, max_lat, min_lon, max_lon, max_tamanho=800 ):
        tam = self.area_em_pixeis(min_lat,max_lat,min_lon,max_lon)
        if tam[0]>tam[1]:
          if tam[0]>max_tamanho:
            tam[1]=round(max_tamanho*tam[1]/tam[0])
            tam[0]=max_tamanho
        else:
          if tam[1]>max_tamanho:
            tam[0]=round(max_tamanho*tam[0]/tam[1])
            tam[1]=max_tamanho
        imagem = Image.new("RGBA", (tam[0],tam[1]), (0,0,0,0))
        quadros = self.quadros.loc[(self.quadros["carregado"] == True)]
        for indice, quadro in quadros.iterrows():
          quadro=quadro["objeto"]
          area=self.area_do_poligono(quadro.poligono)
          min_y=round((area[0]-min_lat)*tam[1]/(max_lat-min_lat))
          max_y=round((area[1]-min_lat)*tam[1]/(max_lat-min_lat))
          min_x=round((area[2]-min_lon)*tam[0]/(max_lon-min_lon))
          max_x=round((area[3]-min_lon)*tam[0]/(max_lon-min_lon))
          tam_x=max_x-min_x
          tam_y=max_y-min_y
          redimensionada = quadro.imagem.resize((tam_x,tam_y))
          imagem.paste(redimensionada,(min_x,tam[1]-max_y))
        display(imagem)
        return imagem

class ProjetoCarcara:
      mapa_atual = None
      galeria_gee = None
      def __init__(self, nome_da_pasta, nome_do_projeto=None, ftp=None, gee_sessao=None, area_interesse=None):
        self.ftp = ftp
        self.gee_sessao = gee_sessao
        self.area_interesse = area_interesse
        if ftp is not None and nome_do_projeto is None:
            self.carregar_arquivo(nome_da_pasta, ftp)
        else:
            self.novo_projeto(nome_da_pasta, nome_do_projeto, ftp)

      def salvar_dados_de_novo_projeto(self):
        self.ftp.mkd( self.nome_da_pasta )
        self.ftp.mkd( f"{self.nome_da_pasta}/galeria" )
        self.ftp.mkd( f"{self.nome_da_pasta}/modelo" )

        buffer = io.BytesIO(json.dumps({"nome_do_projeto": self.nome_do_projeto}).encode('utf-8'))
        ftp.storbinary(f'STOR {self.nome_da_pasta}/dados.json', buffer)

        self.galeria.drop(columns=["objeto"]).to_csv("galeria.csv", index=False)
        with open("galeria.csv", 'rb') as file:
            self.ftp.storbinary(f'STOR {nome_da_pasta}/galeria.csv', file)

      def novo_projeto(self, nome_da_pasta, nome_do_projeto, ftp):
        self.nome_do_projeto = nome_do_projeto
        self.nome_da_pasta = nome_da_pasta
        self.galeria = pd.DataFrame( columns=["projeto", "mapa_id", "data", "hora", "resoluÃ§Ã£o_x", "resoluÃ§Ã£o_y", "objeto"] )

        if ftp is not None:
            self.ftp = ftp
            self.salvar_dados_do_novo_projeto()

        else:
            self.ftp = None

      def carregar_arquivo(self, nome_da_pasta, ftp):
          self.nome_da_pasta = nome_da_pasta
          if ftp is not None:
              # Cria um objeto BytesIO para ler 'dados.json'
              with io.BytesIO() as mem_file_json:
                  # LÃª 'dados.json' do servidor FTP para a memÃ³ria
                  ftp.retrbinary(f'RETR {nome_da_pasta}/dados.json', mem_file_json.write)
                  mem_file_json.seek(0)  # Posiciona no inÃ­cio do arquivo em memÃ³ria
                  data = json.load(mem_file_json)  # Carrega o JSON em memÃ³ria

              # Atualiza o nome do projeto com base nos dados carregados
              self.nome_do_projeto = data["nome_do_projeto"]
              if "area_interesse" in data:
                self.area_interesse = data["area_interesse"]

              # Cria um novo objeto BytesIO para ler 'galeria.csv'
              with io.BytesIO() as mem_file_csv:
                  # LÃª 'galeria.csv' do servidor FTP para a memÃ³ria
                  ftp.retrbinary(f'RETR {nome_da_pasta}/galeria.csv', mem_file_csv.write)
                  mem_file_csv.seek(0)  # Posiciona no inÃ­cio do arquivo em memÃ³ria
                  self.galeria = pd.read_csv(mem_file_csv)  # Carrega o CSV em um DataFrame
                  self.galeria["objeto"] = None

      def adicionar_ftp(self, ftp):
        if self.ftp is None:
            self.ftp = ftp
            self.salvar_dados_do_novo_projeto()

      def adicionar_gee_sessao(self, gee_sessao):
        self.gee_sessao = gee_sessao

      def adicionar_area_de_interesse(self, area_interesse):
        self.area_interesse = area_interesse

      def adicionar_mapa(self, mapa):
        if(self.galeria[self.galeria["mapa_id"]==mapa.mapa_id[0]].shape[0]>0):
            return False
        self.mapa_atual = mapa.mapa_id[0]
        self.galeria = pd.concat([self.galeria, pd.DataFrame([{"projeto": mapa.projeto, "mapa_id": mapa.mapa_id[0], "data": mapa.data, "hora": mapa.hora, "resoluÃ§Ã£o_x": mapa.escala[0], "resoluÃ§Ã£o_y": mapa.escala[1], "objeto": mapa}])])
        return True

      def salvar_dados_do_projeto(self):
        if self.ftp is not None:
            buffer = io.BytesIO(json.dumps({"nome_do_projeto": self.nome_do_projeto, "area_interesse": self.area_interesse}).encode('utf-8'))
            self.ftp.storbinary(f'STOR {self.nome_da_pasta}/dados.json', buffer)

            self.galeria.drop(columns=["objeto"]).to_csv("galeria.csv", index=False)
            with open("galeria.csv", 'rb') as file:
                self.ftp.storbinary(f'STOR {self.nome_da_pasta}/galeria.csv', file)

      def salvar_dados_do_mapa(self, mapa_id):
        mapa = self.galeria[self.galeria["mapa_id"]==mapa_id].iloc[0]['objeto']
        mapa_id = str.replace(mapa_id, "/", "+")
        try:
            self.ftp.cwd( f"{self.nome_da_pasta}/galeria/{mapa_id}" )
        except ftplib.error_perm:
            self.ftp.mkd( f"{self.nome_da_pasta}/galeria/{mapa_id}" )

        self.ftp.cwd("/")

        try:
            self.ftp.cwd( f"{self.nome_da_pasta}/galeria/{mapa_id}/mascaras" )
        except ftplib.error_perm:
            self.ftp.mkd( f"{self.nome_da_pasta}/galeria/{mapa_id}/mascaras" )

        self.ftp.cwd("/")

        buffer = io.BytesIO(json.dumps({"projeto": mapa.projeto, "mapa_id": mapa.mapa_id, "geometria": mapa.geometria, "data": mapa.data, "hora": mapa.hora, "escala": mapa.escala, "quadro": mapa.quadro, "bands": mapa.bands, "ranges": mapa.ranges}).encode('utf-8'))
        self.ftp.storbinary(f'STOR {self.nome_da_pasta}/galeria/{mapa_id}/dados.json', buffer)

        mapa.quadros.drop(columns=["objeto", "carregado"]).to_csv("quadros.csv", index=False)
        with open("quadros.csv", 'rb') as file:
            self.ftp.storbinary(f'STOR {self.nome_da_pasta}/galeria/{mapa_id}/quadros.csv', file)

        mapa.mascaras.drop(columns=["objeto", "carregado"]).to_csv("mascaras.csv", index=False)
        with open("mascaras.csv", 'rb') as file:
            self.ftp.storbinary(f'STOR {self.nome_da_pasta}/galeria/{mapa_id}/mascaras.csv', file)

      def carregar_dados_do_mapa(self, mapa_id):
        mapa_pasta = str.replace(mapa_id, "/", "+")
        if self.ftp is not None:
              # Cria um objeto BytesIO para ler 'dados.json'
              with io.BytesIO() as mem_file_json:
                  # LÃª 'dados.json' do servidor FTP para a memÃ³ria
                  self.ftp.retrbinary(f'RETR {self.nome_da_pasta}/galeria/{mapa_pasta}/dados.json', mem_file_json.write)
                  mem_file_json.seek(0)  # Posiciona no inÃ­cio do arquivo em memÃ³ria
                  dados = json.load(mem_file_json)  # Carrega o JSON em memÃ³ria

              imagem = ImagemSatelite(dados['projeto'],dados['mapa_id'],dados=dados)
              if dados['quadro'] is not None:
                  imagem.definir_quadro(dados['quadro'][0],dados['quadro'][1])

              # Cria um novo objeto BytesIO para ler 'galeria.csv'
              with io.BytesIO() as mem_file_csv:
                  # LÃª 'galeria.csv' do servidor FTP para a memÃ³ria
                  self.ftp.retrbinary(f'RETR {self.nome_da_pasta}/galeria/{mapa_pasta}/quadros.csv', mem_file_csv.write)
                  mem_file_csv.seek(0)  # Posiciona no inÃ­cio do arquivo em memÃ³ria
                  imagem.quadros = pd.read_csv(mem_file_csv)  # Carrega o CSV em um DataFrame
                  imagem.quadros["objeto"] = imagem.quadros.apply(lambda row: QuadroSatelite(row["indice_lat"], row["indice_lon"], imagem.poligono_do_quadro(row["indice_lat"], row["indice_lon"])), axis=1)
                  imagem.quadros["carregado"] = False

              # Cria um novo objeto BytesIO para ler 'mascaras.csv'
              with io.BytesIO() as mem_file_csv:
                  # LÃª 'mascaras.csv' do servidor FTP para a memÃ³ria
                  self.ftp.retrbinary(f'RETR {self.nome_da_pasta}/galeria/{mapa_pasta}/mascaras.csv', mem_file_csv.write)
                  mem_file_csv.seek(0)  # Posiciona no inÃ­cio do arquivo em memÃ³ria
                  imagem.mascaras = pd.read_csv(mem_file_csv)  # Carrega o CSV em um DataFrame
                  imagem.mascaras["objeto"] = imagem.mascaras.apply(lambda row: MascaraCategorica(row["nome"], imagem=imagem), axis=1)
                  imagem.mascaras["carregado"] = False

              self.galeria.loc[self.galeria["mapa_id"]==mapa_id, "objeto"] = imagem

      def salvar_quadros_do_mapa(self, mapa_id):
          mapa_pasta = mapa_id.replace("/", "+")
          mapa = self.galeria[self.galeria["mapa_id"] == mapa_id].iloc[0]['objeto']

          if self.ftp is not None:
              condicao = (mapa.quadros["carregado"] == True) & (mapa.quadros["salvo"] == False)
              quadros = mapa.quadros.loc[condicao]

              for indice, quadro in quadros.iterrows():
                  if quadro["carregado"]:
                      arquivo = quadro["objeto"].nome_do_arquivo()
                      buffer = io.BytesIO()  # Cria um buffer em memÃ³ria para a imagem
                      quadro["objeto"].imagem.save(buffer, format='PNG')  # Salva a imagem no buffer como PNG
                      buffer.seek(0)  # Retorna ao inÃ­cio do buffer para garantir que a leitura dos bytes comece do inÃ­cio

                      # Agora, buffer contÃ©m a representaÃ§Ã£o em bytes da imagem, pronto para ser enviado via FTP
                      path = f'{self.nome_da_pasta}/galeria/{mapa_pasta}/{arquivo}.png'
                      if self.ftp.storbinary(f'STOR {path}', buffer):
                          idx = quadro.name  # 'name' contÃ©m o Ã­ndice da linha original no DataFrame 'mapa.quadros'
                          mapa.quadros.loc[idx, "salvo"] = True

      def carregar_quadros_salvos_do_mapa(self, mapa_id):
          mapa_pasta = mapa_id.replace("/", "+")
          mapa = self.galeria[self.galeria["mapa_id"] == mapa_id].iloc[0]['objeto']

          if self.ftp is not None:
              condicao = (mapa.quadros["carregado"] == False) & (mapa.quadros["salvo"] == True)
              quadros = mapa.quadros.loc[condicao]

              for indice, quadro in quadros.iterrows():
                  if not quadro["carregado"]:
                      arquivo = quadro["objeto"].nome_do_arquivo()
                      path = f'{self.nome_da_pasta}/galeria/{mapa_pasta}/{arquivo}.png'
                      with io.BytesIO() as buffer:
                          self.ftp.retrbinary(f'RETR {path}', buffer.write)
                          buffer.seek(0)  # Volta ao inÃ­cio do buffer
                          quadro["objeto"].carregarImagem(Image.open(buffer).copy())

                      idx = quadro.name  # 'name' contÃ©m o Ã­ndice da linha original no DataFrame 'mapa.quadros'
                      mapa.quadros.loc[idx, "carregado"] = True

      def salvar_mascaras_do_mapa(self, mapa_id):
          mapa_pasta = mapa_id.replace("/", "+")
          mapa = self.galeria[self.galeria["mapa_id"] == mapa_id].iloc[0]['objeto']

          if self.ftp is not None:
              mascaras = mapa.mascaras.loc[(mapa.mascaras["carregado"] == True)]

              for indice, mascara in mascaras.iterrows():
                  try:
                      self.ftp.cwd( f"{self.nome_da_pasta}/galeria/{mapa_pasta}/mascaras/{mascara['nome']}" )
                  except ftplib.error_perm:
                      self.ftp.mkd( f"{self.nome_da_pasta}/galeria/{mapa_pasta}/mascaras/{mascara['nome']}" )

                  self.ftp.cwd("/")

                  mascara['objeto'].categorias.to_csv("categorias.csv", index=False)
                  with open("categorias.csv", 'rb') as file:
                      self.ftp.storbinary(f'STOR {self.nome_da_pasta}/galeria/{mapa_pasta}/mascaras/{mascara["nome"]}/categorias.csv', file)

                  quadros = mascara['objeto'].quadros.loc[(mascara['objeto'].quadros["carregado"]==True)&(mascara['objeto'].quadros["salvo"]==False)]

                  for indice, quadro in quadros.iterrows():
                      if quadro["carregado"]:
                          arquivo = quadro["objeto"].nome_do_arquivo()
                          buffer = io.BytesIO(bytes(quadro['objeto'].imagem))

                          # Criar outro buffer em memÃ³ria para a versÃ£o compactada
                          buffer_gz = io.BytesIO()

                          # Compactar os dados da imagem e escrevÃª-los no buffer_gz
                          with gzip.GzipFile(fileobj=buffer_gz, mode='wb') as f_out:
                              # Copiar os dados do buffer da imagem para o buffer gz
                              f_out.write(buffer.getvalue())

                          # Certificar-se de que o ponteiro do buffer estÃ¡ no inÃ­cio
                          buffer_gz.seek(0)

                          # Agora, buffer contÃ©m a representaÃ§Ã£o em bytes da imagem, pronto para ser enviado via FTP
                          path = f'{self.nome_da_pasta}/galeria/{mapa_pasta}/mascaras/{mascara["nome"]}/{arquivo}.gz'
                          if self.ftp.storbinary(f'STOR {path}', buffer_gz):
                              idx = quadro.name  # 'name' contÃ©m o Ã­ndice da linha original no DataFrame 'mapa.quadros'
                              mascara['objeto'].quadros.loc[idx, "salvo"] = True

                  mascara['objeto'].quadros.drop(columns=["objeto", "carregado"]).to_csv("quadros.csv", index=False)
                  with open("quadros.csv", 'rb') as file:
                      self.ftp.storbinary(f'STOR {self.nome_da_pasta}/galeria/{mapa_pasta}/mascaras/{mascara["nome"]}/quadros.csv', file)

      def carregar_mascaras_salvas_do_mapa(self, mapa_id):
          mapa_pasta = mapa_id.replace("/", "+")
          mapa = self.galeria[self.galeria["mapa_id"] == mapa_id].iloc[0]['objeto']

          if self.ftp is not None:
              mascaras = mapa.mascaras.loc[(mapa.mascaras["carregado"] == False)]

              for indice, mascara in mascaras.iterrows():
                  with io.BytesIO() as mem_file_csv:
                      # LÃª 'galeria.csv' do servidor FTP para a memÃ³ria
                      self.ftp.retrbinary(f'RETR {self.nome_da_pasta}/galeria/{mapa_pasta}/mascaras/{mascara["nome"]}/quadros.csv', mem_file_csv.write)
                      mem_file_csv.seek(0)  # Posiciona no inÃ­cio do arquivo em memÃ³ria
                      mascara['objeto'].quadros = pd.read_csv(mem_file_csv)  # Carrega o CSV em um DataFrame
                      mascara['objeto'].quadros["objeto"] = mascara['objeto'].quadros.apply(lambda row: QuadroSatelite(row["indice_lat"], row["indice_lon"], mapa.poligono_do_quadro(row["indice_lat"], row["indice_lon"])), axis=1)
                      mascara['objeto'].quadros["carregado"] = False

                  with io.BytesIO() as mem_file_csv:
                      # LÃª 'galeria.csv' do servidor FTP para a memÃ³ria
                      self.ftp.retrbinary(f'RETR {self.nome_da_pasta}/galeria/{mapa_pasta}/mascaras/{mascara["nome"]}/categorias.csv', mem_file_csv.write)
                      mem_file_csv.seek(0)  # Posiciona no inÃ­cio do arquivo em memÃ³ria
                      mascara['objeto'].categorias = pd.read_csv(mem_file_csv)  # Carrega o CSV em um DataFrame

                  quadros = mascara['objeto'].quadros.loc[(mascara['objeto'].quadros["carregado"] == False)&(mascara['objeto'].quadros["salvo"] == True)]

                  for indice, quadro in quadros.iterrows():
                      if not quadro["carregado"]:
                          arquivo = quadro["objeto"].nome_do_arquivo()
                          path = f'{self.nome_da_pasta}/galeria/{mapa_pasta}/mascaras/{mascara.nome}/{arquivo}.gz'
                          with io.BytesIO() as buffer:
                              self.ftp.retrbinary(f'RETR {path}', buffer.write)
                              buffer.seek(0)  # Volta ao inÃ­cio do buffer

                              # Descompactar o conteÃºdo do .gz
                              with gzip.GzipFile(fileobj=buffer) as f_gz:
                                  dados_descompactados = f_gz.read()  # Ler os bytes descompactados
                                  quadro["objeto"].carregarImagem(list(dados_descompactados))

                          idx = quadro.name  # 'name' contÃ©m o Ã­ndice da linha original no DataFrame 'mapa.quadros'
                          mascara['objeto'].quadros.loc[idx, "carregado"] = True

      def abrirMapa(self, mapa_id, carregar_quadros=True):
        self.carregar_dados_do_mapa(mapa_id)
        if carregar_quadros:
          self.carregar_quadros_salvos_do_mapa(mapa_id)
          self.carregar_mascaras_salvas_do_mapa(mapa_id)
        self.mapa_atual = mapa_id
        return self.galeria[self.galeria["mapa_id"]==self.mapa_atual].iloc[0]["objeto"]

      def novoMapa(self, projeto, mapa_id, geometria, quadro=None):
        imagem = ImagemSatelite(projeto, mapa_id, geometria=geometria)
        if quadro is not None:
          imagem.definir_quadro(quadro[0],quadro[1])
        self.adicionar_mapa(imagem)
        self.mapa_atual = mapa_id
        return self.galeria[self.galeria["mapa_id"]==self.mapa_atual].iloc[0]["objeto"]

      def salvarMapa(self):
        if self.mapa_atual is not None:
          self.salvar_dados_do_mapa(self.mapa_atual)
          self.salvar_quadros_do_mapa(self.mapa_atual)
          self.salvar_mascaras_do_mapa(self.mapa_atual)
          self.salvar_dados_do_mapa(self.mapa_atual)
        self.salvar_dados_do_projeto()

      def mapaAtual(self):
        if self.mapa_atual is not None:
          return self.galeria[self.galeria["mapa_id"]==self.mapa_atual].iloc[0]["objeto"]

      def carregarArea(self, min_lat, max_lat, min_lon, max_lon, carregar=True):
        if self.mapa_atual is not None:
          mapa = self.galeria[self.galeria["mapa_id"]==self.mapa_atual].iloc[0]["objeto"]
          area = mapa.indices_da_area(min_lat, max_lat, min_lon, max_lon)
          for quadro in area:
            mapa.gerar_quadro_pelos_indices(quadro[0], quadro[1])
          if carregar:
            for quadro in area:
              mapa.carregar_quadro(quadro[0], quadro[1])

      def explorarGaleriaGEE(self, asset_id, project="projects/earthengine-public", area_interesse=None, startTime="2000-01-01T00:00:00.000Z", endTime="2050-01-01T00:00:00.000Z", filter="CLOUDY_PIXEL_PERCENTAGE < 10"):
        if area_interesse is None:
          area_interesse = self.area_interesse

        name = '{}/assets/{}'.format(project, asset_id)
        url = 'https://earthengine.googleapis.com/v1alpha/{}:listImages?{}'.format(
          name, urllib.parse.urlencode({
            'startTime': startTime,        # Imagens a partir desta data
            'endTime': endTime,         # Imagens atÃ© esta data.
            'region': str({'type': 'Polygon',
              'coordinates': [[[area_interesse[2], area_interesse[0]],
                              [area_interesse[3], area_interesse[0]],
                              [area_interesse[3], area_interesse[1]],
                              [area_interesse[2], area_interesse[1]],
                              [area_interesse[2], area_interesse[0]]]]}),
            'filter': filter,       # Filtro para as imagens
        }))
        response = self.gee_sessao.get(url)
        content = json.loads(response.content)
        display(content)

        if 'images' in content:
          self.galeria_gee = pd.DataFrame(content['images'])
          self.galeria_gee['endTime'] = pd.to_datetime(self.galeria_gee['endTime'])
          self.galeria_gee['startTime'] = pd.to_datetime(self.galeria_gee['startTime'])
          self.galeria_gee['updateTime'] = pd.to_datetime(self.galeria_gee['updateTime'])
          return self.galeria_gee
        return response

      def plotarGaleriaGEE(self, nuvens=20, df=None):
        if df is None:
          df = self.galeria_gee

        df = pd.DataFrame({"Dia": df['endTime'], "Nuvens": df['properties']}).sort_values('Dia')
        df['Dia'] = df['Dia'].dt.tz_localize(None).dt.to_period('D')
        df['Nuvens'] = df['Nuvens'].apply(lambda x: x['CLOUDY_PIXEL_PERCENTAGE'])
        df = df.groupby('Dia')['Nuvens'].mean().reset_index()
        df["Mes"] = df['Dia'].apply(lambda x: x.start_time.to_period('M'))
        df['Viavel'] = df['Nuvens']<=nuvens
        df['Periodo'] = df['Dia'].diff(+1)

        # Agrupando por 'Mes' para o total de dias e dias viÃ¡veis
        df_total = df.groupby('Mes').size()
        df_viavel = df[df['Viavel']].groupby('Mes').size()

        # Garantindo que ambos os DataFrames tenham o mesmo Ã­ndice completo de meses
        periodo_completo = pd.period_range(start=df["Mes"].min(), end=df["Mes"].max(), freq='M')
        df_total = df_total.reindex(periodo_completo, fill_value=0)
        df_viavel = df_viavel.reindex(periodo_completo, fill_value=0)

        # Calculando estatÃ­sticas
        min_val = df_total.min()
        max_val = df_total.max()
        mean_val = df_total.mean()
        mode_val = df_total.mode()[0]  # Assume apenas um valor para simplificaÃ§Ã£o
        std_val = df_total.std()

        # Plotando o grÃ¡fico
        plt.figure(figsize=(25, 6))
        # Barras pretas para o total de observaÃ§Ãµes
        df_total.plot(kind='bar', color='black', label='Total de ObservaÃ§Ãµes', width=0.9, position=0)
        # Barras azuis para observaÃ§Ãµes viÃ¡veis
        df_viavel.plot(kind='bar', color='blue', label=f'Nuvens <= {nuvens}%', width=0.7, position=-0.1)

        # Linhas para os valores estatÃ­sticos
        plt.axhline(y=min_val, color='blue', linestyle='--', label=f'MÃ­nimo = {min_val}')
        plt.axhline(y=max_val, color='red', linestyle='--', label=f'MÃ¡ximo = {max_val}')
        plt.axhline(y=mean_val, color='green', linestyle='--', label=f'MÃ©dia = {round(mean_val,4)}')
        plt.axhline(y=mode_val, color='purple', linestyle='--', label=f'Moda = {mode_val}')
        plt.axhline(y=mean_val+std_val, color='orange', linestyle='--', label=f'Desvio padrÃ£o = {round(std_val,4)}')
        plt.axhline(y=mean_val-std_val, color='orange', linestyle='--')

        plt.title('DistribuiÃ§Ã£o de observaÃ§Ãµes por mÃªs')
        plt.xlabel('MÃªs')
        plt.ylabel('NÃºmero de ObservaÃ§Ãµes')
        plt.xticks(rotation=45)
        plt.legend(loc='upper left')
        plt.show()

        df2 = df[1:].copy()

        # ConversÃ£o da coluna 'Dia' para tipo datetime
        df2['Dia'] = df2['Dia'].dt.to_timestamp()
        df2['Periodo'] = df2['Periodo'].apply(lambda x: x.n)

        # Plotagem do grÃ¡fico
        plt.figure(figsize=(25, 6))  # Configura o tamanho do grÃ¡fico
        plt.plot(df2['Dia'], df2['Periodo'], linestyle='-', color='b')  # 'o' para os marcadores, '-' para linha sÃ³lida

        plt.title('PerÃ­odo entre as imagens')  # Adiciona um tÃ­tulo ao grÃ¡fico
        plt.xlabel('Data da imagem')  # Nomeia o eixo x
        plt.ylabel('Tempo desde a imagem anterior em dias')  # Nomeia o eixo y
        plt.grid(True)  # Adiciona uma grade ao grÃ¡fico para melhor leitura

        plt.show()  # Exibe o grÃ¡fico

        return df

      def salvarDFGaleriaGEE(self, nome_arquivo_destino, df=None):
        if df is None:
          df=self.galeria_gee

        # Convertendo o DataFrame para um objeto StringIO (um arquivo em memÃ³ria)
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)  # Retorna ao inÃ­cio do arquivo em memÃ³ria para garantir que tudo seja lido

        # Convert the string buffer to bytes
        data_in_bytes = output.getvalue().encode()

        # FunÃ§Ã£o para mostrar o progresso da transferÃªncia
        def handle_binary(more_data):
            progress_handler(len(more_data))  # Chama a funÃ§Ã£o de progresso

        # FunÃ§Ã£o para atualizar e exibir o progresso da transferÃªncia
        def progress_handler(block):
            print(f"Transferido {block} bytes...")

        # Conectando ao servidor FTP
        self.ftp.set_pasv(True)  # Ativa o modo passivo

        # Convert the StringIO object to BytesIO for binary transfer
        bytes_io = io.BytesIO(data_in_bytes)

        # Inicia a transferÃªncia usando um objeto BytesIO
        self.ftp.storbinary(f'STOR {nome_arquivo_destino}', bytes_io)

        print(f"Arquivo *{nome_arquivo_destino}* salvo.")
        return True

      def abrirDFGaleriaGEE(self, nome_arquivo_destino, fixar=True):
          # Cria um objeto BytesIO para armazenar os dados binÃ¡rios baixados
          bytes_io = io.BytesIO()

          # FunÃ§Ã£o para ler os dados baixados e armazenÃ¡-los no objeto BytesIO
          def handle_binary(data):
              bytes_io.write(data)

          # Conectando ao servidor FTP e setando o modo passivo
          self.ftp.set_pasv(True)

          # Inicia o download do arquivo usando um objeto BytesIO
          self.ftp.retrbinary(f'RETR {nome_arquivo_destino}', handle_binary)

          # Retorna ao inÃ­cio do objeto BytesIO para garantir que tudo seja lido
          bytes_io.seek(0)

          # Converte o objeto BytesIO para StringIO para poder usar com pandas
          string_io = io.StringIO(bytes_io.getvalue().decode())

          # LÃª o DataFrame do objeto StringIO
          df = pd.read_csv(string_io)
          df['endTime'] = pd.to_datetime(df['endTime'])
          df['startTime'] = pd.to_datetime(df['startTime'])
          df['updateTime'] = pd.to_datetime(df['updateTime'])
          df['properties'] = df['properties'].apply(lambda x: json.loads(x.replace("'",'"')))
          df['geometry'] = df['geometry'].apply(lambda x: json.loads(x.replace("'",'"')))
          df['bands'] = df['bands'].apply(lambda x: json.loads(x.replace("'",'"')))

          if fixar:
            self.galeria_gee = df

          return df

      def preverImagem(self, imagem_id, geometria=None, projeto="projects/earthengine-public", area_interesse=None, bands=['B4', 'B3', 'B2'], ranges=[{'min': 1500, 'max': 3000}]):
          if area_interesse is None:
            area_interesse = self.area_interesse
          imagem = ImagemSatelite(projeto, imagem_id, geometria=geometria, bands=bands, ranges=ranges)
          self.ultima_previsao = imagem
          return (imagem, imagem.preverMapa(area_interesse[0], area_interesse[1], area_interesse[2], area_interesse[3]))

      def preverImagemNaData(self, data, df=None, bands=['B4', 'B3', 'B2'], ranges=[{'min': 1500, 'max': 3000}]):
          if df is None:
            df=self.galeria_gee

          imagens = df[(df['endTime']>data)&(df['endTime']<(datetime.strptime(data, "%Y-%m-%d").date()+timedelta(days=1)).strftime("%Y-%m-%d"))]

          imagem_id = imagens['id'].tolist()
          geometria = imagens['geometry'].tolist()

          display(imagens)
          return projeto.preverImagem(imagem_id, geometria=geometria, bands=bands, ranges=ranges)

      def adicionarMapaPrevisto(self, carregar=True):
          display(self.adicionar_mapa(self.ultima_previsao))
          display(self.galeria)
          self.carregarArea(self.area_interesse[0], self.area_interesse[1], self.area_interesse[2], self.area_interesse[3], carregar)
          if carregar:
            self.ultima_previsao.visualizarMapa(self.area_interesse[0], self.area_interesse[1], self.area_interesse[2], self.area_interesse[3])
          return self.ultima_previsao