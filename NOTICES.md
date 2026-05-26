# Third-Party Notices

This project includes portions of code from:

---

## lanqian528/chat2api

- **License:** MIT License
- **Copyright:** Copyright (c) 2024 aurora-develop
- **Source:** https://github.com/lanqian528/chat2api
- **Files derived from upstream:**
  - `gpt2agent/_vendored/pow.py` — ported from `chatgpt/proofofWork.py`
  - `gpt2agent/_vendored/turnstile.py` — ported from `chatgpt/turnstile.py`

**Modifications:** removed `diskcache`, `pybase64`, `ua_generator`, and `utils.*`
dependencies in favor of the Python standard library; reduced to the minimum
surface needed to produce Sentinel `proof` and `turnstile` tokens.

### Full MIT License Text (lanqian528/chat2api)

```
MIT License

Copyright (c) 2024 aurora-develop

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

---

NOTE ON LICENSING: Portions of this project (vendored solver code in
`gpt2agent/_vendored/`) are under the MIT License as reproduced above.
The rest of the project is under the terms in `LICENSE`. Downstream users
of the vendored files may continue to use them under MIT regardless of any
additional restrictions the containing project imposes on its original code.
