"""
Provides Solidity specific instantiation of the LanguageServer class.
Contains various configurations and settings specific to Solidity.
"""

import asyncio
import json
import logging
import os
import pathlib
import shutil
import subprocess
from contextlib import asynccontextmanager
from typing import AsyncIterator

from multilspy.language_server import LanguageServer
from multilspy.lsp_protocol_handler.server import ProcessLaunchInfo
from multilspy.multilspy_config import MultilspyConfig
from multilspy.multilspy_logger import MultilspyLogger
from multilspy.multilspy_utils import FileUtils, PlatformUtils


class SolidityLanguageServer(LanguageServer):
    """
    Provides Solidity specific instantiation of the LanguageServer class.
    Contains various configurations and settings specific to Solidity.
    """

    def __init__(self, config: MultilspyConfig, logger: MultilspyLogger, repository_root_path: str):
        """
        Creates a SolidityLanguageServer instance. This class is not meant to be instantiated directly.
        Use LanguageServer.create() instead.
        """

        # Store repository root for project setup
        self.repository_root_path = repository_root_path

        executable_path = self.setup_runtime_dependencies(logger)

        super().__init__(
            config,
            logger,
            repository_root_path,
            ProcessLaunchInfo(cmd=executable_path, cwd=repository_root_path),
            "solidity",
        )

    def setup_runtime_dependencies(self, logger: MultilspyLogger) -> str:
        """
        Setup runtime dependencies for SolidityLanguageServer.
        """
        logger.log("Setting up Solidity language server runtime dependencies...", logging.INFO)

        platform_id = PlatformUtils.get_platform_id()
        logger.log(f"Detected platform: {platform_id.value}", logging.INFO)

        node_path = shutil.which("node")
        if node_path is None:
            raise RuntimeError("Node.js is required to run the Solidity language server. Please install Node.js and try again.")

        npm_path = shutil.which("npm")
        if npm_path is None:
            raise RuntimeError("npm is required to prepare the Solidity language server. Please install npm and try again.")

        # To switch between Solidity LSP implementations, change the filename here:
        # - "runtime_dependencies.json" for VSCode Solidity (juanfranblanco/vscode-solidity)
        # - "runtime_dependencies_nomic.json" for Nomic Foundation (@nomicfoundation/solidity-language-server)
        with open(os.path.join(os.path.dirname(__file__), "runtime_dependencies.json"), "r") as f:
            d = json.load(f)
            del d["_description"]

        # Check if platform is supported
        supported_platforms = [dep["platformId"] for dep in d["runtimeDependencies"]]
        if platform_id.value not in supported_platforms:
            raise RuntimeError(f"Unsupported platform: {platform_id.value}. Supported platforms: {supported_platforms}")

        # Find the dependency for the current platform
        runtime_dependencies = d["runtimeDependencies"]
        dependency = next((dep for dep in runtime_dependencies if dep["platformId"] == platform_id.value), None)
        if dependency is None:
            raise RuntimeError(f"No runtime dependency found for platform {platform_id.value}")

        # Setup paths
        solidity_ls_dir = os.path.join(os.path.dirname(__file__), "static", "vscode-solidity")
        os.makedirs(solidity_ls_dir, exist_ok=True)

        primary_extraction_path = os.path.join(solidity_ls_dir, dependency["relative_extraction_path"])
        server_script_relative_path = dependency["serverScript"]
        server_script_parts = server_script_relative_path.split("/")
        legacy_relative_paths = dependency.get("legacyRelativeExtractionPaths", [])

        def run_command_with_logging(command, cwd: str, use_shell: bool = False):
            display_cmd = command if isinstance(command, str) else " ".join(command)
            logger.log(f"Executing command: {display_cmd}", logging.INFO)
            process = subprocess.Popen(
                command,
                cwd=cwd,
                shell=use_shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )
            assert process.stdout is not None
            try:
                for line in process.stdout:
                    logger.log(line.rstrip(), logging.INFO)
            finally:
                process.stdout.close()

            exit_code = process.wait()
            if exit_code != 0:
                raise RuntimeError(f"Command '{display_cmd}' failed with exit code {exit_code}")

        def resolve_paths():
            candidate_relative_paths = [dependency["relative_extraction_path"], *legacy_relative_paths]
            for relative_path in candidate_relative_paths:
                candidate_extraction_path = os.path.join(solidity_ls_dir, relative_path)
                candidate_server_path = os.path.join(candidate_extraction_path, *server_script_parts)
                if os.path.exists(candidate_server_path):
                    return candidate_extraction_path, candidate_server_path
            default_extraction_path = os.path.join(solidity_ls_dir, dependency["relative_extraction_path"])
            default_server_path = os.path.join(default_extraction_path, *server_script_parts)
            return default_extraction_path, default_server_path

        extraction_path, server_script_path = resolve_paths()

        if not os.path.exists(server_script_path):
            logger.log("Solidity language server entry point not found, preparing installation...", logging.INFO)
            if not os.path.exists(primary_extraction_path):
                logger.log("VSCode Solidity extension not found locally. Downloading archive...", logging.INFO)
                logger.log(f"Download URL: {dependency['url']}", logging.INFO)
                FileUtils.download_and_extract_archive(
                    logger, dependency["url"], solidity_ls_dir, dependency["archiveType"]
                )
            else:
                logger.log("VSCode Solidity directory exists but server build output missing.", logging.WARNING)

            extraction_path, server_script_path = resolve_paths()

        if not os.path.exists(extraction_path):
            raise FileNotFoundError(f"VSCode Solidity extension was not found at {extraction_path} after extraction")

        npm_install_dirs = dependency.get("npmInstallDirs", [])
        for relative_dir in npm_install_dirs:
            install_path = os.path.join(extraction_path, relative_dir)
            node_modules_path = os.path.join(install_path, "node_modules")
            if not os.path.isdir(install_path):
                raise FileNotFoundError(f"Expected npm install directory {install_path} does not exist")
            if not os.path.exists(node_modules_path) or not os.listdir(node_modules_path):
                logger.log(f"Installing npm dependencies in {install_path}...", logging.INFO)
                try:
                    run_command_with_logging([npm_path, "install"], install_path)
                    logger.log("npm install completed successfully.", logging.INFO)
                except Exception as exc:
                    logger.log(f"npm install failed for {install_path}: {exc}", logging.ERROR)
                    raise RuntimeError(f"npm install failed in {install_path}") from exc
            else:
                logger.log(f"npm dependencies already installed in {install_path}, skipping.", logging.INFO)

        if not os.path.exists(server_script_path):
            compile_command = dependency.get("compileCommand")
            compile_working_dir = dependency.get("compileWorkingDirectory", ".")
            if compile_command:
                compile_path = os.path.join(extraction_path, compile_working_dir)
                if not os.path.isdir(compile_path):
                    raise FileNotFoundError(f"Compile working directory {compile_path} does not exist")
                logger.log(f"Building Solidity language server via '{compile_command}' in {compile_path}...", logging.INFO)
                try:
                    run_command_with_logging(compile_command, compile_path, use_shell=True)
                    logger.log("Solidity language server build completed successfully.", logging.INFO)
                except Exception as exc:
                    logger.log(f"Compilation command failed in {compile_path}: {exc}", logging.ERROR)
                    raise RuntimeError(f"Failed to compile Solidity language server in {compile_path}") from exc

        if not os.path.exists(server_script_path):
            raise FileNotFoundError(f"Solidity language server entry point not found at {server_script_path}")

        logger.log(f"Solidity language server ready. Entry point: {server_script_path}", logging.INFO)

        # Setup project dependencies for Nomic Foundation LSP
        # self._setup_project_dependencies(logger)

        quoted_node_path = f"\"{node_path}\""
        quoted_server_path = f"\"{server_script_path}\""
        return f"{quoted_node_path} {quoted_server_path} --stdio"

    def _setup_project_dependencies(self, logger: MultilspyLogger) -> None:
        """
        Setup project dependencies (Hardhat) in the repository for Nomic Foundation LSP
        """
        logger.log("Setting up project dependencies for Nomic Foundation LSP...", logging.INFO)

        npm_path = shutil.which("npm")
        if npm_path is None:
            logger.log("npm not found, skipping project setup", logging.WARNING)
            return

        # Check if package.json exists in the repository
        package_json_path = os.path.join(self.repository_root_path, "package.json")
        if not os.path.exists(package_json_path):
            logger.log("No package.json found, creating one with Hardhat dependency...", logging.INFO)
            # Create a minimal package.json
            package_json_content = {
                "name": "solidity-project",
                "version": "1.0.0",
                "description": "Solidity project for multilspy",
                "devDependencies": {
                    "hardhat": "^2.17.0",
                    "@nomicfoundation/hardhat-toolbox": "^3.0.0"
                },
                "scripts": {
                    "compile": "hardhat compile"
                }
            }

            with open(package_json_path, "w") as f:
                json.dump(package_json_content, f, indent=2)
            logger.log("Created package.json with Hardhat dependency", logging.INFO)
        else:
            # Check if hardhat is already in dependencies
            try:
                with open(package_json_path, "r") as f:
                    package_json = json.load(f)

                dev_deps = package_json.get("devDependencies", {})
                deps = package_json.get("dependencies", {})

                if "hardhat" not in dev_deps and "hardhat" not in deps:
                    logger.log("Adding Hardhat to existing package.json...", logging.INFO)
                    if "devDependencies" not in package_json:
                        package_json["devDependencies"] = {}
                    package_json["devDependencies"]["hardhat"] = "^2.17.0"
                    package_json["devDependencies"]["@nomicfoundation/hardhat-toolbox"] = "^3.0.0"

                    with open(package_json_path, "w") as f:
                        json.dump(package_json, f, indent=2)
                    logger.log("Added Hardhat to package.json", logging.INFO)
                else:
                    logger.log("Hardhat already found in package.json", logging.INFO)

            except Exception as exc:
                logger.log(f"Error reading package.json: {exc}", logging.WARNING)
                return

        # Check if node_modules exists and has hardhat
        node_modules_path = os.path.join(self.repository_root_path, "node_modules")
        hardhat_path = os.path.join(node_modules_path, "hardhat")

        if not os.path.exists(hardhat_path):
            logger.log("Installing project dependencies (this may take a moment)...", logging.INFO)
            try:
                def run_npm_install(command, cwd: str):
                    import subprocess
                    logger.log(f"Running: {' '.join(command) if isinstance(command, list) else command}", logging.INFO)
                    result = subprocess.run(command, cwd=cwd, shell=isinstance(command, str), capture_output=True, text=True)
                    if result.returncode != 0:
                        raise RuntimeError(f"Command failed: {result.stderr}")
                    return result.stdout

                run_npm_install([npm_path, "install"], self.repository_root_path)
                logger.log("Project dependencies installed successfully", logging.INFO)
            except Exception as exc:
                logger.log(f"Failed to install project dependencies: {exc}", logging.WARNING)
        else:
            logger.log("Project dependencies already installed", logging.INFO)

        # Create basic hardhat.config.js if it doesn't exist
        hardhat_config_path = os.path.join(self.repository_root_path, "hardhat.config.js")
        if not os.path.exists(hardhat_config_path):
            logger.log("Creating basic hardhat.config.js...", logging.INFO)
            hardhat_config_content = '''require("@nomicfoundation/hardhat-toolbox");

/** @type import('hardhat/config').HardhatUserConfig */
module.exports = {
  solidity: "0.8.19",
};
'''
            with open(hardhat_config_path, "w") as f:
                f.write(hardhat_config_content)
            logger.log("Created basic hardhat.config.js", logging.INFO)

    def _get_initialize_params(self, repository_absolute_path: str):
        """
        Returns the initialize params for the Solidity Language Server.
        """
        # Use corresponding initialize params file for the selected LSP
        with open(os.path.join(os.path.dirname(__file__), "initialize_params.json"), "r") as f:
            d = json.load(f)

        del d["_description"]

        d["processId"] = os.getpid()
        d["rootPath"] = repository_absolute_path
        d["rootUri"] = pathlib.Path(repository_absolute_path).as_uri()
        d["workspaceFolders"][0]["uri"] = pathlib.Path(repository_absolute_path).as_uri()
        d["workspaceFolders"][0]["name"] = os.path.basename(repository_absolute_path)

        return d

    @asynccontextmanager
    async def start_server(self) -> AsyncIterator["SolidityLanguageServer"]:
        """
        Starts the Solidity Language Server, waits for the server to be ready and yields the LanguageServer instance.
        """

        async def do_nothing(params):
            return

        async def window_log_message(msg):
            self._log_window_message(msg)

        async def publish_diagnostics(params):
            """Handle diagnostics published by the language server"""
            if isinstance(params, dict) and 'uri' in params and 'diagnostics' in params:
                uri = params['uri']
                diagnostics = params['diagnostics']
                if diagnostics:
                    self.logger.log(f"Diagnostics for {uri}: {len(diagnostics)} issues found", logging.INFO)
                    for diag in diagnostics[:5]:  # Log first 5 diagnostics to avoid spam
                        message = diag.get('message', 'Unknown diagnostic')
                        severity = diag.get('severity', 1)
                        severity_name = ['Error', 'Warning', 'Info', 'Hint'][min(severity, 3)]
                        line = diag.get('range', {}).get('start', {}).get('line', '?')
                        self.logger.log(f"  Line {line}: {severity_name} - {message}", logging.INFO)

        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", publish_diagnostics)

        async with super().start_server():
            self.logger.log("Starting Solidity Language Server process", logging.INFO)
            await self.server.start()
            initialize_params = self._get_initialize_params(self.repository_root_path)

            self.logger.log(
                "Sending initialize request from LSP client to LSP server and awaiting response",
                logging.INFO,
            )
            init_response = await self.server.send.initialize(initialize_params)

            # Verify server capabilities
            if "capabilities" not in init_response:
                raise RuntimeError("Invalid initialize response from Solidity language server")

            capabilities = init_response["capabilities"]
            self.logger.log(f"Solidity language server capabilities: {list(capabilities.keys())}", logging.INFO)

            self.server.notify.initialized({})
            self.completions_available.set()

            yield self

            try:
                await asyncio.wait_for(self.server.shutdown(), timeout=5)
            except asyncio.TimeoutError:
                self.logger.log("Timed out waiting for Solidity language server to shutdown gracefully.", logging.WARNING)
            finally:
                await self.server.stop()
