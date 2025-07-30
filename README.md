# Istaroth

Istaroth is a Retrieval-Augmented Generation (RAG) system for Genshin Impact that extracts, cleans, and structures textual content to answer lore questions about the world of Teyvat.

## Getting Started

### Python Environment Setup

- Clone repository and install dependencies: `pip install -r requirements.txt`
- Install pre-commit hooks (if you plan on doing development): `pre-commit install`
- Set required environment variable: `export ISTAROTH_DOCUMENT_STORE="/path/to/document/store"`
- Optional LangSmith tracing: Set `LANGSMITH_API_KEY`, `LANGCHAIN_PROJECT`, `LANGCHAIN_TRACING_V2="true"`

### Checkpoint

A checkpoint currently mainly consists of the vectorstore containing cleaned game texts and their vector embeddings. You can either grab a pre-trained checkpoint from the [release page](https://github.com/isundaylee/istaroth/releases), or follow the sections below to train your own. If you grab a pre-trained checkpoint, be sure to use it with the corresponding Git commit hash. Currently pre-trained checkpoints are only provided for the Chinese language.

#### Checkpoint Training

- Set some env vars:
    - `export AGD_PATH="/path/to/AnimeGameData"`
    - `export AGD_LANGUAGE="CHS"` (or `ENG` for English)
- Process AGD data: `scripts/agd_tools.py generate-all /path/to/text/files` to extract and clean text files
- Add documents: `scripts/rag_tools.py add-documents /path/to/text/files`

### Running Queries

- Set some env vars:
    - `GOOGLE_API_KEY` to a Google API key with Gemini API enabled
    - `ISTAROTH_TRAINING_DEVICE=cpu` if you don't have CUDA
- Basic query: `scripts/rag_tools.py query "玛丽安与西摩尔的关系是怎么样的？"`
    - Query with sources: `scripts/rag_tools.py query "玛丽安与西摩尔的关系是怎么样的？" --show-sources`
- Retrieve documents only: `scripts/rag_tools.py retrieve "璃月港的历史" --k 3`
    - Parameters: `--k` (documents to retrieve, default 5), `--show-sources` (display similarity scores)

## MCP Server

Istaroth includes an MCP (Model Context Protocol) server that allows Claude to query the RAG system directly. The server supports both local (stdio) and remote (HTTP/WebSocket) connections.

### Docker image

You can launch an MCP server with a prebuilt Docker image:

```
docker run -p 8000:8000 isundaylee/istaroth:latest
```

Then follow the remaining instructions in the Remote MCP server section below to add it into Claude.

The Docker image defaults to loading a recent Chinese checkpoint upon first startup. You can customize it by setting the `ISTAROTH_CHECKPOINT_URL` env var.

### Local MCP Server (stdio)

For local Claude Code integration:

- Copy the MCP wrapper template: `cp scripts/mcp_wrapper.template.sh scripts/mcp_wrapper.sh`
- Edit `scripts/mcp_wrapper.sh` and set your environment variables.
- Add the MCP server to Claude Code: `claude mcp add istaroth /path/to/istaroth/scripts/mcp_wrapper.sh`
- Restart Claude Code to enable the MCP server

### Remote MCP Server (HTTP/WebSocket)

For remote access or web-based integrations:

- Start the HTTP/WebSocket server: `fastmcp run scripts/mcp_server.py --transport=streamable-http`
- Add the MCP server to Claude Code: `claude mcp add istaroth --transport=http http://127.0.0.1:8000/mcp`
- Restart Claude Code to enable the MCP server

### Usage

Once configured, you can query the Istaroth knowledge base directly in Claude using natural language. The MCP server provides a `retrieve` function that searches the document store for relevant content.

## Example Query

Here's an example output to the query "玛丽安与西摩尔的关系是怎么样的？":

> 回答: 根据提供的资料，玛丽安与西摩尔的关系如下：
>
> 1.  **守护者与被守护者：** 西摩尔是由玛丽安的“老哥”阿兰·吉约丹（即玛丽安·吉约丹的哥哥）所设计并制造的机械造物。西摩尔的首要指令便是“代替阿兰·吉约丹陪伴在小姐身边，保护小姐”，而这位“小姐”就是玛丽安（资料1、资料2、资料4）。
> 2.  **深厚的感情与依赖：**
>     *   **西摩尔对玛丽安的忠诚与依恋：** 即使在玛丽安解除其所有指令后，西摩尔依然表达了“我想继续陪伴在您的身边，玛丽安小姐”的愿望（资料1）。他高度重视玛丽安的指示，即便在被调侃时也会认真执行（如“乖狗狗，坐下”并询问原因，资料3、资料5）。当他担心因性能问题被废弃时，也向玛丽安寻求确认，显示出对她的信任与依赖（资料2）。
>     *   **玛丽安对西摩尔的关爱与情感：** 玛丽安对西摩尔的态度充满温情与爱护。她亲昵地称呼西摩尔为“笨狗”、“乖狗狗”（资料1、资料2、资料3、资料5），并明确表示“对不起。我很想你…”（资料2），表达了深切的思念。她鼓励西摩 尔“成为自己命运的主人”，去做他“想”做的事情，体现了对西摩尔自主性的尊重和对未来幸福的期盼（资料1）。她也坚定地向西摩尔保证“当然不会！”废弃他（资料2）。
> 3.  **跨越时间与形态的羁绊：** 西摩尔一直在寻找玛丽安。尽管安（纯水精灵）在当前形态下并未与西摩尔有过记忆中的会面，但安却能立即认出西摩尔是“笨狗西摩尔”，而西摩尔也认出了他所寻找的“玛丽安小姐”（资料3、资料4、资料5）。这暗示了他们之间存在着超越形态和当前记忆的深层联系与羁绊。
>
> 综上所述，玛丽安与西摩尔的关系是一种由创造者指令起始，但随着时间推移和情感发展，演变为深厚、互相关爱、充满依恋与信任的独特关系。西摩尔是玛丽安的忠实守护者，而玛丽安则是西摩尔所珍视和依赖的主人，彼此之间存在着深刻的情感连接。
>
> 使用的资料源 (5 个):
>
> 【资料1】(相似度: 0.7729)
> 安: ……
> 安: 就由你来说吧，玛丽安。因为，对西摩尔而言，我只是安而已。
> 「玛丽安」: 西摩尔，你想做什么？
> 西摩尔: 我的首要指令是代替阿兰·吉约丹陪伴在小姐身边，保护小姐。
> 「玛丽安」: 笨蛋，这是老哥…是阿兰的指令。我想问的是，你「想」做什么？
> 西摩尔: …我曾经答应玛梅赫小姐，在找到主人以后，我会返回她之前的空间坐标，向她表达谢意。
> 「玛丽安」: 你做得很对，乖狗狗。
> 西摩尔: ？
> 安:...
>
> <truncated...>
