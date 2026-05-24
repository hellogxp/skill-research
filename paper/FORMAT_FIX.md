# ARR 格式修复说明

## 问题

`paper/main.tex` 第 5 行使用了错误的 ACL style 选项：

```latex
\usepackage[hyperref]{acl}
```

## 正确写法

```latex
\usepackage[review]{acl}
```

## 原因

- `[review]` 是 ARR 投稿的正式选项，会添加**行号**（审稿人必须能通过行号引用内容）+ 匿名模式 + 内部自动加载 hyperref
- `[hyperref]` 是旧版 acl.sty 的用法，2023+ 版本不再需要手动传该选项；传了之后**不会生成行号**，可能导致 desk reject

## 修改范围

仅改 `paper/main.tex` 第 5 行，一处，其余不动。

## 验证

编译后确认 PDF 左侧有行号即为正确。

## 参考

llm-mi/paper-emnlp/main.tex 使用的是 `\usepackage[review]{acl}`，格式正确。
