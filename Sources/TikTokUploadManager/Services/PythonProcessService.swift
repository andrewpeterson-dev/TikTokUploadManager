import Foundation

final class PythonProcessService {

    private var process: Process?
    private var pipe: Pipe?
    private let pythonExecutableURL: URL
    private let scriptURL: URL

    init(pythonExecutableURL: URL? = nil, scriptURL: URL? = nil) {
        self.pythonExecutableURL = pythonExecutableURL ?? Self.defaultPythonExecutableURL()
        self.scriptURL = scriptURL ?? Self.defaultScriptURL()
    }

    func runScript(
        arguments: [String],
        outputHandler: @escaping (String) -> Void,
        completion: @escaping () -> Void
    ) {
        guard process == nil else {
            DispatchQueue.main.async {
                outputHandler("A Python process is already running.\\n")
            }
            return
        }

        guard FileManager.default.fileExists(atPath: scriptURL.path) else {
            DispatchQueue.main.async {
                outputHandler("Python script not found: \(self.scriptURL.path)\\n")
                completion()
            }
            return
        }

        let process = Process()
        let pipe = Pipe()

        process.executableURL = pythonExecutableURL
        process.arguments = [scriptURL.path] + arguments
        process.currentDirectoryURL = scriptURL.deletingLastPathComponent()
        process.standardOutput = pipe
        process.standardError = pipe

        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONUNBUFFERED"] = "1"

        // Ensure ffmpeg and other tools are in PATH
        let homeDir = FileManager.default.homeDirectoryForCurrentUser.path
        let userBinPath = "\(homeDir)/bin"
        let brewBinPath = "/opt/homebrew/bin"
        let usrLocalBin = "/usr/local/bin"

        if let existingPath = environment["PATH"] {
            environment["PATH"] = "\(userBinPath):\(brewBinPath):\(usrLocalBin):\(existingPath)"
        } else {
            environment["PATH"] = "\(userBinPath):\(brewBinPath):\(usrLocalBin):/usr/bin:/bin"
        }

        process.environment = environment

        pipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            if let output = String(data: data, encoding: .utf8), !output.isEmpty {
                DispatchQueue.main.async {
                    outputHandler(output)
                }
            }
        }

        process.terminationHandler = { [weak self] process in
            DispatchQueue.main.async {
                outputHandler("\\nProcess exited with code \(process.terminationStatus).\\n")
                completion()
            }
            self?.cleanup()
        }

        do {
            try process.run()
            self.process = process
            self.pipe = pipe
        } catch {
            DispatchQueue.main.async {
                outputHandler("Failed to start Python process: \(error)\\n")
                completion()
            }
            cleanup()
        }
    }

    func stop() {
        process?.terminate()
        cleanup()
    }

    private func cleanup() {
        pipe?.fileHandleForReading.readabilityHandler = nil
        pipe = nil
        process = nil
    }

    private static func defaultPythonExecutableURL() -> URL {
        let env = ProcessInfo.processInfo.environment
        if let configured = env["TIKTOK_PYTHON_EXECUTABLE"], !configured.isEmpty {
            return URL(fileURLWithPath: configured)
        }

        let candidates = [
            "/opt/homebrew/bin/python3",
            "/usr/local/bin/python3",
            "/usr/bin/python3",
            "/Applications/Xcode.app/Contents/Developer/usr/bin/python3"
        ]

        for candidate in candidates {
            if FileManager.default.fileExists(atPath: candidate) {
                return URL(fileURLWithPath: candidate)
            }
        }

        return URL(fileURLWithPath: "/usr/bin/python3")
    }

    private static func defaultScriptURL() -> URL {
        let env = ProcessInfo.processInfo.environment
        if let configured = env["TIKTOK_PYTHON_SCRIPT"], !configured.isEmpty {
            return URL(fileURLWithPath: configured)
        }

        let fileManager = FileManager.default

        if let bundledScript = Bundle.main.resourceURL?.appendingPathComponent("Python/clip_generator_cli.py"),
           fileManager.fileExists(atPath: bundledScript.path) {
            return bundledScript
        }

        let projectScript = URL(fileURLWithPath: "\(NSHomeDirectory())/TikTokUploadManager/Python/clip_generator_cli.py")
        if fileManager.fileExists(atPath: projectScript.path) {
            return projectScript
        }

        return projectScript
    }
}
