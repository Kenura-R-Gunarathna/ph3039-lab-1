// ==========================================
// 1. COMPACT UI COMPONENTS
// ==========================================
#let alert(type: "info", title: none, body) = {
  let (c, bg, t) = if type == "warning" {
    (rgb("#d97706"), rgb("#fffbeb"), "Warning")
  } else if type == "success" {
    (rgb("#16a34a"), rgb("#f0fdf4"), "Result")
  } else if type == "danger" {
    (rgb("#dc2626"), rgb("#fef2f2"), "Important")
  } else {
    (rgb("#2563eb"), rgb("#eff6ff"), "Note")
  }
  block(
    width: 100%, fill: bg, above: 9pt, below: 6pt,
    stroke: (left: 2pt + c, rest: 0.4pt + c.lighten(60%)),
    inset: (x: 8pt, y: 6pt), radius: (right: 3pt),
    text(size: 8.5pt)[#text(weight: "bold", fill: c)[#if title != none { title } else { t }.] #body],
  )
}

// Small stat card; use inside a grid for a metric row.
#let metric(label, value, delta: none) = block(
  fill: rgb("#f8fafc"), stroke: 0.4pt + rgb("#e2e8f0"),
  inset: (x: 4pt, y: 3pt), radius: 3pt, width: 100%,
  align(center)[
    #text(5.5pt, fill: rgb("#64748b"), weight: "bold")[#upper(label)] \
    #text(10pt, weight: "bold", fill: rgb("#0f172a"))[#value]
    #if delta != none [ \ #text(6pt, fill: rgb("#16a34a"))[#delta]]
  ],
)

#let badge(content, color: rgb("#2563eb")) = box(
  fill: color.lighten(85%), stroke: 0.4pt + color.lighten(40%),
  inset: (x: 3pt, y: 1pt), radius: 2pt, baseline: 0%,
  text(size: 6.5pt, weight: "bold", fill: color.darken(20%))[#content],
)

// Row of full-width figures (spans both columns). Each item: (path, caption).
#let fig-row(..items, gap: 5pt, cols: none) = {
  let items = items.pos()
  figure(
    grid(
      columns: if cols != none { cols } else { items.map(_ => 1fr) }, column-gutter: gap, align: horizon,
      ..items.map(it => image(it.at(0), width: 100%)),
    ),
    caption: items.enumerate().map(((i, it)) => [(#str.from-unicode(97 + i)) #it.at(1)]).join([ ]),
    placement: auto, scope: "parent",
  )
}

// ==========================================
// 2. MAIN TEMPLATE  (A4, 2 columns, tight spacing)
// ==========================================
#let report_template(
  title: "",
  assignment: "",
  author: "Kenura R. Gunarathna",
  index_no: "s17239",
  department: "Faculty of Science",
  columns: 2,
  body,
) = {
  set page(
    paper: "a4",
    margin: (top: 1.8cm, bottom: 1.7cm, left: 1.8cm, right: 1.8cm),
    footer: context align(center, text(6.5pt, fill: rgb("#64748b"))[
      #title --- #index_no #h(1fr) #counter(page).display("1 / 1", both: true)
    ]),
    footer-descent: 25%,
  )

  set text(font: ("Libertinus Serif", "Times New Roman"), size: 9.5pt, lang: "en")
  set par(justify: true, leading: 0.62em, spacing: 0.85em, first-line-indent: 0pt)
  set list(indent: 2pt, body-indent: 3pt, spacing: 0.35em, marker: [•])
  set enum(indent: 2pt, body-indent: 3pt, spacing: 0.35em)

  show heading: set text(fill: rgb("#0f172a"))
  show heading.where(level: 1): it => block(
    width: 100%, above: 13pt, below: 6pt, sticky: true,
    stroke: (bottom: 0.4pt + rgb("#cbd5e1")), inset: (bottom: 3pt),
    text(size: 10pt, weight: "bold", it.body),
  )
  show heading.where(level: 2): it => block(
    above: 9pt, below: 4pt, sticky: true,
    text(size: 9pt, weight: "bold", fill: rgb("#1e293b"), it.body),
  )
  show heading.where(level: 3): it => block(
    above: 6pt, below: 3pt, sticky: true,
    text(size: 8pt, style: "italic", weight: "bold", it.body),
  )

  show raw: set text(font: ("JetBrainsMono NF", "Menlo"), size: 6.8pt)
  show raw.where(block: false): it => box(
    fill: rgb("#f1f5f9"), inset: (x: 1.5pt), outset: (y: 1.5pt), radius: 1.5pt,
    text(fill: rgb("#b91c1c"), it),
  )
  show raw.where(block: true): it => block(
    width: 100%, fill: rgb("#f8fafc"), stroke: 0.4pt + rgb("#cbd5e1"),
    inset: 4pt, radius: 2pt, it,
  )

  set table(
    stroke: (x, y) => if y == 0 { (bottom: 0.8pt + rgb("#334155")) } else { 0.3pt + rgb("#e2e8f0") },
    fill: (col, row) => if row == 0 { rgb("#f1f5f9") } else if calc.odd(row) { rgb("#f8fafc") } else { none },
    inset: (x: 4pt, y: 3.2pt),
  )
  show table: set text(size: 7.5pt)

  set math.equation(numbering: "(1)", supplement: [Eq.])
  show math.equation.where(block: true): set block(above: 7pt, below: 7pt)
  show math.equation: set text(size: 8.2pt)

  set figure(gap: 5pt)
  show figure: set block(above: 9pt, below: 9pt)
  show figure.caption: it => text(size: 7.2pt, fill: rgb("#475569"))[
    *#it.supplement #context it.counter.display(it.numbering).* #it.body
  ]
  show figure.where(kind: table): set figure.caption(position: top)

  // Title block spans both columns
  place(top + center, scope: "parent", float: true,
    block(width: 100%, below: 6pt)[
      #v(2pt)
      #text(14pt, weight: "bold", fill: rgb("#0f172a"))[#title] \
      #text(9pt, fill: rgb("#334155"))[#assignment]
      #h(8pt) #text(8pt)[*#author* | #index_no | #text(fill: rgb("#64748b"))[#department]]
      #v(4pt)
      #line(length: 100%, stroke: 0.4pt + rgb("#cbd5e1"))
    ]
  )

  if columns > 1 { std.columns(columns, gutter: 16pt, body) } else { body }
}
