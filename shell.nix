{ pkgs ? import <nixpkgs> {} }:
let
  pythonEnv = pkgs.python3.withPackages (ps: with ps; [
    requests
    colorama 
    python-dotenv
  ]);
in
pkgs.mkShell {
  buildInputs = [
    pythonEnv
    pkgs.git
  ];
  shellHook = ''
    export PYTHONPATH=${pythonEnv}/${pythonEnv.sitePackages}
    export PATH=$PATH:${pythonEnv}/bin
  '';
}
