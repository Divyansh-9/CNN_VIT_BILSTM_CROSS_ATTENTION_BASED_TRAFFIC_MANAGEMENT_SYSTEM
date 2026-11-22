# Third-party notices

## Phosphor Icons

`src/icons.jsx` holds the path data of four icons from Phosphor Icons, regular
weight, version 2.1.1 of `@phosphor-icons/core`: `broadcast`,
`clock-counter-clockwise`, `chart-bar` and `traffic-signal`. They are copied,
not installed, so the dashboard has no icon dependency (D-6).

```
MIT License

Copyright (c) 2023 Phosphor Icons

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Fonts: Inter, JetBrains Mono

Self-hosted from the `@fontsource-variable/inter` and `@fontsource-variable/jetbrains-mono`
packages (5.3.0, pinned in `package.json`) and
bundled into `dist/`, so the page fetches no font from outside. Both are licensed
under the SIL Open Font License 1.1 (https://openfontlicense.org):

- Inter: Copyright 2020 The Inter Project Authors (https://github.com/rsms/inter)
- JetBrains Mono: Copyright 2020 The JetBrains Mono Project Authors (https://github.com/JetBrains/JetBrainsMono)

The full licence text ships with each package, in `node_modules/@fontsource-variable/*/LICENSE`.
