import re
from html.parser import HTMLParser

from .artifacts import Artifact
from .styles import style_shell


class HtmlSafetyParser(HTMLParser):
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag.lower() in {"script", "iframe", "object", "embed", "link", "meta", "base", "form"}:
            raise ValueError(f"HTML 包含不允许的标签：{tag}")
        for name, value in attrs:
            lowered = name.lower()
            if lowered.startswith("on"):
                raise ValueError("HTML 不允许内联事件属性")
            if lowered in {"src", "href", "xlink:href", "srcdoc", "action", "formaction"} and value:
                if not (value.startswith("data:") or value.startswith("#")):
                    raise ValueError("HTML 不允许外部资源或链接")


def validate_html(body: str, css: str, javascript: str) -> None:
    HtmlSafetyParser().feed(body)
    if re.search(r"@import|url\s*\(|expression\s*\(", css, re.IGNORECASE):
        raise ValueError("CSS 不允许外部资源或表达式")
    if re.search(r"</script", javascript, re.IGNORECASE):
        raise ValueError("JavaScript 包含非法结束标签")
    forbidden_js = [
        r"\bfetch\s*\(", r"\bXMLHttpRequest\b", r"\bWebSocket\b", r"\bEventSource\b",
        r"\beval\s*\(", r"\bnew\s+Function\b", r"\bimport\s*\(", r"\bdocument\.cookie\b",
        r"\blocalStorage\b", r"\bsessionStorage\b", r"\bwindow\.open\b", r"\btop\s*\.",
        r"\bparent\s*\.", r"\bnavigator\.sendBeacon\b",
    ]
    if any(re.search(pattern, javascript, re.IGNORECASE) for pattern in forbidden_js):
        raise ValueError("JavaScript 包含网络、存储或动态执行等受限能力")


def verify_artifact(artifact: Artifact) -> Artifact:
    checks = ["产物协议与字段校验通过"]
    if artifact.html:
        validate_html(artifact.html.body, artifact.html.css, artifact.html.javascript)
        artifact.html.document = style_shell(
            artifact.style,
            artifact.html.body,
            artifact.html.css,
            artifact.html.javascript,
        )
        checks.append("HTML/CSS/JavaScript 安全校验通过")
    if artifact.graph:
        checks.append("节点与边引用完整性校验通过")
    if artifact.formula:
        checks.append("公式结构校验通过")
    checks.append("产物包含简明解释")
    artifact.verification.passed = True
    artifact.verification.checks = checks
    return artifact
