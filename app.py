import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State, callback
import plotly.express as px
import pandas as pd
import io
import base64

# --- CONFIGURAÇÕES E CONSTANTES ---
CATEGORIAS_EXCLUIR = ['CAIXA SORVETE/AÇAI', 'CAIXA DE PIZZA']

# Inicializa a aplicação Dash com um tema profissional
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LITERA], suppress_callback_exceptions=True)
server = app.server # Essencial para o deploy com Gunicorn

# --- DEFINIÇÃO DO LAYOUT DA APLICAÇÃO ---
app.layout = dbc.Container([
    dcc.Store(id='store-dados-processados'),
    
    # Cabeçalho
    dbc.Row(
        dbc.Col(
            html.Div([
                html.Img(src='https://i.ibb.co/zWJstk81/logo-nicopel-8.png', height="50px"),
                html.H1("Dashboard de Desempenho - Nicopel Embalagens", className="text-white ms-3")
            ], style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'center'}),
            style={'backgroundColor': "#34D315", 'padding': '15px', 'borderRadius': '5px', 'textAlign': 'center', 'marginBottom': '20px'}
        )
    ),
    
    dbc.Row([
        # Painel de Controle (Sidebar)
        dbc.Col([
            html.H3("Painel de Controle", className="mb-4"),
            dbc.Alert([
                html.H5("Instruções de Uso", className="alert-heading"),
                html.P("Baixe o arquivo de Itens Faturados e siga os passos:"),
                html.Ul([
                    html.Li("Garanta que o arquivo tenha as colunas necessárias (ex: FRANQUIA, R$ Total, etc.)."),
                    html.Li("Carregue o arquivo no botão abaixo."),
                    html.Li("Use os filtros para analisar.")
                ]),
            ], color="info"),
            
            html.H4("Carregar Arquivo", className="mt-4"),
            dcc.Upload(
                id='upload-data',
                children=html.Div(['Arraste e solte ou ', html.A('selecione um arquivo')]),
                style={'width': '100%', 'height': '60px', 'lineHeight': '60px', 'borderWidth': '2px', 'borderStyle': 'dashed', 'borderRadius': '5px', 'textAlign': 'center', 'margin': '10px 0'}
            ),
            html.Div(id='output-data-upload', className="text-muted small mt-2"),
            html.Hr(),
            
            html.H4("Filtros", className="mt-4"),
            html.Label("Selecione as Franquias:"),
            dcc.Dropdown(id='dropdown-franquias', multi=True, placeholder="Selecione..."),
            html.Label("Selecione os Produtos (Opcional):", className="mt-3"),
            dcc.Dropdown(id='dropdown-itens', multi=True, placeholder="Selecione..."),
            html.Hr(),
            
            dbc.Button("Baixar Relatório em Excel", id="btn-download-excel", color="primary", className="w-100 mt-3"),
            dcc.Download(id="download-excel")
        ], width=12, lg=3, style={'backgroundColor': '#f8f9fa', 'padding': '20px', 'borderRadius': '5px'}),

        # Área de Conteúdo Principal (Dashboard)
        dbc.Col(
            dcc.Loading(
                id="loading-icon",
                children=[html.Div(id='dashboard-content', children=dbc.Alert("Aguardando o carregamento do arquivo e a seleção de filtros...", color="secondary", className="m-4 text-center"))],
                type="default"
            ),
            width=12, lg=9
        )
    ])
], fluid=True, className="p-4")

# --- FUNÇÕES DE PROCESSAMENTO DE DADOS ---
def parse_contents(contents, filename):
    content_type, content_string = contents.split(',')
    decoded = base64.b64decode(content_string)
    try:
        df = pd.read_excel(io.BytesIO(decoded)) if 'xls' in filename else pd.read_csv(io.StringIO(decoded.decode('utf-8')))
        df.columns = [str(col).strip() for col in df.columns]

        colunas_necessarias = ['Data Emissao', 'R$ Total', 'FRANQUIA', 'Categoria', 'Descrição Item']
        if not all(col in df.columns for col in colunas_necessarias):
            missing_cols = [col for col in colunas_necessarias if col not in df.columns]
            return None, f"Erro: Colunas não encontradas: {', '.join(missing_cols)}"

        df['Data Emissao'] = pd.to_datetime(df['Data Emissao'], dayfirst=True, errors='coerce')
        df['R$ Total'] = pd.to_numeric(df['R$ Total'], errors='coerce')
        df.dropna(subset=colunas_necessarias, inplace=True)
        return df, f"Arquivo '{filename}' carregado."
    except Exception as e:
        return None, f'Ocorreu um erro ao processar o arquivo: {e}'

# --- CALLBACKS ---

# Callback 1: Processa o arquivo e popula os filtros
@callback(
    [Output('output-data-upload', 'children'),
     Output('store-dados-processados', 'data'),
     Output('dropdown-franquias', 'options'),
     Output('dropdown-itens', 'options')],
    Input('upload-data', 'contents'),
    State('upload-data', 'filename')
)
def processa_arquivo_enviado(contents, filename):
    if contents:
        df, message = parse_contents(contents, filename)
        if df is not None:
            franquias_unicas = sorted(df['FRANQUIA'].unique())
            opcoes_franquias = [{'label': i, 'value': i} for i in franquias_unicas]
            
            itens_unicos = sorted(df['Descrição Item'].unique())
            opcoes_itens = [{'label': i, 'value': i} for i in itens_unicos]
            
            return dbc.Alert(message, color="success"), df.to_json(date_format='iso', orient='split'), opcoes_franquias, opcoes_itens
        return dbc.Alert(message, color="danger"), None, [], []
    return "", None, [], []

# Callback 2: Atualiza o dashboard
@callback(
    Output('dashboard-content', 'children'),
    Input('store-dados-processados', 'data'),
    Input('dropdown-franquias', 'value'),
    Input('dropdown-itens', 'value')
)
def atualiza_dashboard(jsonified_data, franquias_selecionadas, itens_selecionados):
    if not jsonified_data or not franquias_selecionadas:
        return dbc.Alert("⬅️ Por favor, carregue um arquivo e selecione uma ou mais franquias.", color="info", className="m-4 text-center")

    df = pd.read_json(jsonified_data, orient='split')
    df['Data Emissao'] = pd.to_datetime(df['Data Emissao'], errors='coerce')
    
    df_filtrado = df[df['FRANQUIA'].isin(franquias_selecionadas)]
    if itens_selecionados:
        df_filtrado = df_filtrado[df_filtrado['Descrição Item'].isin(itens_selecionados)]
    regex = '|'.join(CATEGORIAS_EXCLUIR)
    df_filtrado = df_filtrado[~df_filtrado['Categoria'].str.contains(regex, case=False, na=False)]

    if df_filtrado.empty:
        return dbc.Alert("Nenhum dado encontrado para os filtros selecionados.", color="warning", className="m-4 text-center")
        
    # Cálculos
    total_geral = df_filtrado['R$ Total'].sum()
    total_por_franquia = df_filtrado.groupby('FRANQUIA')['R$ Total'].sum().sort_values(ascending=False)
    
    # Layout
    return html.Div([
        dbc.Row([
            dbc.Col(dbc.Card([dbc.CardHeader("Faturamento Total"), dbc.CardBody([html.H4(f"R$ {total_geral:,.2f}", className="card-title")])], color="primary", inverse=True)),
            dbc.Col(dbc.Card([dbc.CardHeader("Franquias Analisadas"), dbc.CardBody([html.H4(len(franquias_selecionadas), className="card-title")])], color="info", inverse=True)),
        ], className="mb-4 g-4"),
        dbc.Row([
            dbc.Col(dcc.Graph(figure=px.bar(
                total_por_franquia.reset_index(), x='R$ Total', y='FRANQUIA', orientation='h',
                title='Ranking de Faturamento Total', template='plotly_white'
            ).update_layout(yaxis={'categoryorder':'total ascending'}, title_x=0.5)), width=12, lg=6),
            dbc.Col(dcc.Graph(figure=px.bar(
                df_filtrado.groupby('Categoria')['R$ Total'].sum().nlargest(10).reset_index(),
                x='R$ Total', y='Categoria', orientation='h', title='Top 10 Categorias por Faturamento', template='plotly_white'
            ).update_layout(yaxis={'categoryorder':'total ascending'}, title_x=0.5)), width=12, lg=6),
        ], className="mt-4")
    ])

# Callback 3: Download do Excel
@callback(
    Output("download-excel", "data"),
    Input("btn-download-excel", "n_clicks"),
    [State('store-dados-processados', 'data'),
     State('dropdown-franquias', 'value'),
     State('dropdown-itens', 'value')],
    prevent_initial_call=True,
)
def gera_excel_para_download(n_clicks, jsonified_data, franquias_selecionadas, itens_selecionados):
    if not n_clicks or not jsonified_data or not franquias_selecionadas:
        raise dash.exceptions.PreventUpdate
        
    df = pd.read_json(jsonified_data, orient='split')
    df_original = df.copy()
    
    df['Data Emissao'] = pd.to_datetime(df['Data Emissao'], errors='coerce')
    df_filtrado = df[df['FRANQUIA'].isin(franquias_selecionadas)]
    if itens_selecionados:
        df_filtrado = df_filtrado[df_filtrado['Descrição Item'].isin(itens_selecionados)]
    regex = '|'.join(CATEGORIAS_EXCLUIR)
    df_final = df_filtrado[~df_filtrado['Categoria'].str.contains(regex, case=False, na=False)]
    
    output_buffer = io.BytesIO()
    with pd.ExcelWriter(output_buffer, engine='xlsxwriter') as writer:
        df_original.to_excel(writer, sheet_name='Base_Completa', index=False)
        df_final.to_excel(writer, sheet_name='Dados_Filtrados', index=False)
    
    return dcc.send_bytes(output_buffer.getvalue(), "Relatorio_Analitico_Franquias.xlsx")