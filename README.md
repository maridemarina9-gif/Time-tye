# TIME TYE

**Corra. Conecte-se. Supere-se.**

Time Tye é um aplicativo de corrida para registrar percursos reais com GPS,
acompanhar métricas e, opcionalmente, visualizar corredores que escolheram
compartilhar a localização durante uma corrida.

## Funcionalidades do MVP

- Cadastro e login com senha armazenada somente em hash `scrypt`
- Recuperação de senha com token de uso único e expiração de 30 minutos
- Dashboard com corridas, distância, tempo, ritmo e maior distância
- Rastreamento pelo GPS do navegador, sem dados simulados
- Filtro de coordenadas inválidas, baixa precisão, duplicatas e saltos impossíveis
- Distância por Haversine e métricas de ritmo, velocidade, calorias e elevação
- Mapa individual do percurso usando OpenStreetMap/Carto
- Mapa de corredores ao vivo com consentimento explícito e localização aproximada
- Histórico, detalhes, gráficos e exclusão de corridas
- Perfil e configurações de privacidade

## Instalação local

```bash
cd time-tye
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py --server.port 5000
```

No ambiente Replit, o comando de execução configurado é:

```bash
cd time-tye && streamlit run app.py --server.port 8000 --server.address 0.0.0.0
```

O banco SQLite é criado automaticamente em `data/time_tye.db`. Para trocar o
local, defina `TIME_TYE_DB_PATH`.

## Publicar no GitHub e Streamlit Community Cloud

1. Crie um repositório GitHub e envie o conteúdo do diretório `time-tye`.
2. No Streamlit Community Cloud, escolha **Deploy an app**.
3. Selecione o repositório, branch e o arquivo `app.py`.
4. Configure os secrets na área **Advanced settings**, nunca dentro do Git.
5. Publique e teste o acesso à localização em HTTPS.

O SQLite funciona para o MVP local. Em um deploy com múltiplas instâncias ou
necessidade de persistência garantida, migre a camada de dados para PostgreSQL.
A estrutura de acesso ao banco está isolada para facilitar essa evolução.

## GPS e privacidade

O GPS depende da permissão do navegador e pode ser interrompido quando a tela
é bloqueada, o navegador vai para segundo plano, a aba é fechada ou o sistema
economiza bateria. O Streamlit não é um app móvel nativo e não deve ser tratado
como rastreador em segundo plano.

Em celulares, o Chrome bloqueia geolocalização em endereços HTTP locais como
`http://192.168.x.x:8501`. Para liberar o GPS, publique o app com HTTPS ou use
um túnel HTTPS durante o teste.

O padrão é privado. A localização pública só entra no mapa quando o corredor
autoriza o compartilhamento e escolhe a visibilidade pública. O telefone,
e-mail e histórico privado jamais são retornados no mapa público. A opção de
aproximação reduz a precisão exibida para proteger pontos de início e fim.

## Arquitetura

`app.py` coordena as telas do MVP; regras reutilizáveis vivem em `auth/`,
`database/`, `tracking/` e `maps/`. O banco usa consultas parametrizadas e
foreign keys. Para a futura versão Android/iOS, a camada de tracking pode ser
movida para uma API persistente sem alterar as regras de distância e métricas.