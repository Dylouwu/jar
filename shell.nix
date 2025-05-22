{ pkgs ? import <nixpkgs> {} }:
let
  pythonEnv = pkgs.python3.withPackages (ps: with ps; [
    colorama 
    discordpy
    requests
    pyinstaller
    python-dotenv
  ]);
in
pkgs.mkShell {
  buildInputs = [
    pythonEnv
    pkgs.git
    pkgs.patchelf
  ];
  shellHook = ''
    export PYTHONPATH=${pythonEnv}/${pythonEnv.sitePackages}
    export PATH=$PATH:${pythonEnv}/bin
  '';
}
