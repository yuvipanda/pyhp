# (Py)thon (H)ypertext (P)reprocessor

I want PHP style 'quick' template execution, but with Python instead.

![PyHP sample code](docs/images/hello.pyhp.png)

**Warning**: Currently *very* insecure. Do not use.


## Setup

You can set it up for local development with:

1. Fork this repository & clone your fork to your local machine.
2. Setup a virtual environment in your clone:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
   
3. Install the `pyhp` package

   ```bash
   pip install -e . 
   ```
   
4. Run `pyhp`!

   ```bash
   python3 -m pyhp.app
   ```
   
   This should serve the contents of the current directory. You can
   try going to `http://localhost:5000/hi.pyhp` to test it out.
