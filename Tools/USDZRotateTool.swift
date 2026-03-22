import Foundation
import SceneKit
import CoreGraphics
import simd

func loadScene(from inputURL: URL) throws -> SCNScene {
    return try SCNScene(url: inputURL, options: nil)
}

func axisVector(_ axis: String) -> SIMD3<Float> {
    switch axis.lowercased() {
    case "x": return SIMD3<Float>(1, 0, 0)
    case "y": return SIMD3<Float>(0, 1, 0)
    case "z": return SIMD3<Float>(0, 0, 1)
    default:  return SIMD3<Float>(0, 1, 0)
    }
}

func makeRotatedScene(
    from sourceScene: SCNScene,
    degrees1: Float,
    axis1: String,
    degrees2: Float,
    axis2: String
) -> SCNScene {
    let newScene = SCNScene()
    let modelRoot = SCNNode()

    for child in sourceScene.rootNode.childNodes {
        modelRoot.addChildNode(child.clone())
    }

    let radians1 = degrees1 * Float.pi / 180.0
    let radians2 = degrees2 * Float.pi / 180.0

    let q1 = simd_quatf(angle: radians1, axis: axisVector(axis1))
    let q2 = simd_quatf(angle: radians2, axis: axisVector(axis2))

    modelRoot.simdOrientation = q2 * q1

    newScene.rootNode.addChildNode(modelRoot)
    return newScene
}

func exportScene(_ scene: SCNScene, to outputURL: URL) throws {
    let fm = FileManager.default

    if fm.fileExists(atPath: outputURL.path) {
        try fm.removeItem(at: outputURL)
    }

    let success = scene.write(
        to: outputURL,
        options: nil,
        delegate: nil,
        progressHandler: { _, error, _ in
            if let error = error {
                fputs("Export error: \(error.localizedDescription)\n", stderr)
            }
        }
    )

    if !success {
        throw NSError(
            domain: "USDZRotateTool",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "Failed to export USDZ."]
        )
    }
}

@main
struct Main {
    static func main() {
        let args = CommandLine.arguments

        guard args.count >= 7 else {
            print("Usage: usdz_rotate_tool <input.usdz> <output.usdz> <degrees1> <axis1> <degrees2> <axis2>")
            print("Example: usdz_rotate_tool input.usdz output.usdz -90 x -90 y")
            exit(1)
        }

        let inputPath = args[1]
        let outputPath = args[2]
        let degrees1 = Float(args[3]) ?? 0
        let axis1 = args[4]
        let degrees2 = Float(args[5]) ?? 0
        let axis2 = args[6]

        let inputURL = URL(fileURLWithPath: inputPath)
        let outputURL = URL(fileURLWithPath: outputPath)

        guard FileManager.default.fileExists(atPath: inputURL.path) else {
            fputs("Input file not found: \(inputURL.path)\n", stderr)
            exit(2)
        }

        do {
            let scene = try loadScene(from: inputURL)
            let rotatedScene = makeRotatedScene(
                from: scene,
                degrees1: degrees1,
                axis1: axis1,
                degrees2: degrees2,
                axis2: axis2
            )
            try exportScene(rotatedScene, to: outputURL)
            print("Rotated USDZ written to: \(outputURL.path)")
        } catch {
            fputs("Failed: \(error)\n", stderr)
            exit(3)
        }
    }
}