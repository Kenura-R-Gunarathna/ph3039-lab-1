// Look-alike of the lab's Word template "PH 3039 - Thermistor Calibration.docx"
// (US Letter, navy title, blue section headings with a rule, grey sub-headings).
#let lab_report(
  title: "",
  course: "",
  student: "",
  index_no: "",
  partners: "",
  body,
) = {
  set page(
    paper: "us-letter",
    margin: (top: 0.65in, bottom: 0.75in, left: 0.72in, right: 0.72in),
    footer: context align(center, text(8pt, fill: rgb("#4a5568"))[
      #index_no · PH 3039 Thermistor Calibration · Page #counter(page).display() of #counter(page).final().first()
    ]),
  )
  set text(font: ("Arial", "Helvetica"), size: 9pt, lang: "en")
  set par(justify: true, leading: 0.5em, spacing: 0.6em)
  set enum(indent: 4pt, body-indent: 4pt, spacing: 0.4em)
  set list(indent: 4pt, body-indent: 4pt, spacing: 0.4em)

  show heading.where(level: 1): it => block(above: 4pt, below: 7pt, text(size: 16pt, weight: "bold", fill: rgb("#1a365d"), hyphenate: false, it.body))
  show heading.where(level: 2): it => block(above: 8pt, below: 5pt, sticky: true, width: 100%,
    stroke: (bottom: 0.8pt + rgb("#a0a0a0")), inset: (bottom: 3pt),
    text(size: 12pt, weight: "bold", fill: rgb("#2b6cb0"), it.body))
  show heading.where(level: 3): it => block(above: 5pt, below: 2pt, sticky: true,
    text(size: 10pt, weight: "bold", fill: rgb("#2d3748"), it.body))

  set table(
    stroke: 0.5pt + rgb("#a0aec0"),
    fill: (col, row) => if row == 0 { rgb("#edf2f7") } else { none },
    inset: (x: 5pt, y: 2.5pt), align: center + horizon,
  )
  show table: set text(size: 8pt)
  show table.cell.where(y: 0): set text(weight: "bold")

  set math.equation(numbering: none)
  show math.equation.where(block: true): set block(above: 6pt, below: 6pt)
  set figure(gap: 4pt)
  show figure: set block(above: 7pt, below: 7pt)
  show figure.caption: it => text(size: 8pt, style: "italic", fill: rgb("#4a5568"), it)
  show figure.where(kind: table): set figure.caption(position: top)

  // Header block (as in the Word template)
  heading(level: 1, title)
  par(spacing: 0.45em)[*Course Code & Name:* #course]
  par(spacing: 0.45em)[*Student Name:* #student]
  par(spacing: 0.45em)[*Student ID:* #index_no]
  par(spacing: 0.45em)[*Lab Partner(s):* #partners]
  body
}
