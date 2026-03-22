import Foundation
import SceneKit
import AppKit

func makeScene(usdzPath: String) throws -> (SCNScene, SCNNode) {
    let usdzURL = URL(fileURLWithPath: usdzPath)
    let scene = try SCNScene(url: usdzURL, options: nil)

    let containerNode = SCNNode()
    for child in scene.rootNode.childNodes {
        containerNode.addChildNode(child.clone())
    }

    let renderScene = SCNScene()
    renderScene.rootNode.addChildNode(containerNode)

    let (minVec, maxVec) = containerNode.boundingBox
    let center = SCNVector3(
        (minVec.x + maxVec.x) / 2,
        (minVec.y + maxVec.y) / 2,
        (minVec.z + maxVec.z) / 2
    )
    let sizeVec = SCNVector3(
        maxVec.x - minVec.x,
        maxVec.y - minVec.y,
        maxVec.z - minVec.z
    )

    containerNode.position = SCNVector3(-center.x, -center.y, -center.z)

    let cameraNode = SCNNode()
    let camera = SCNCamera()
    camera.zNear = 0.001
    camera.zFar = 1000
    camera.fieldOfView = 24
    cameraNode.camera = camera

    let maxDimension = max(sizeVec.x, max(sizeVec.y, sizeVec.z))
    cameraNode.position = SCNVector3(0, 0, maxDimension * 2.4 + 0.3)
    renderScene.rootNode.addChildNode(cameraNode)

    let keyLightNode = SCNNode()
    let keyLight = SCNLight()
    keyLight.type = .omni
    keyLight.intensity = 180
    keyLight.color = NSColor.white
    keyLightNode.light = keyLight
    keyLightNode.position = SCNVector3(2, 2, 4)
    renderScene.rootNode.addChildNode(keyLightNode)

    let ambientNode = SCNNode()
    let ambient = SCNLight()
    ambient.type = .ambient
    ambient.intensity = 25
    ambient.color = NSColor.white
    ambientNode.light = ambient
    renderScene.rootNode.addChildNode(ambientNode)

    return (renderScene, cameraNode)
}

func renderBitmap(scene: SCNScene, cameraNode: SCNNode, width: CGFloat, height: CGFloat, background: NSColor) throws -> NSBitmapImageRep {
    scene.background.contents = background

    let renderer = SCNRenderer(device: nil, options: nil)
    renderer.scene = scene
    renderer.pointOfView = cameraNode

    let image = renderer.snapshot(
        atTime: 0,
        with: CGSize(width: width, height: height),
        antialiasingMode: .multisampling4X
    )

    guard
        let tiffData = image.tiffRepresentation,
        let bitmap = NSBitmapImageRep(data: tiffData)
    else {
        throw NSError(
            domain: "USDZPosterRenderer",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "Failed to render bitmap"]
        )
    }

    return bitmap
}

func combineBlackWhiteToTransparent(
    blackBitmap: NSBitmapImageRep,
    whiteBitmap: NSBitmapImageRep
) throws -> NSBitmapImageRep {
    let width = blackBitmap.pixelsWide
    let height = blackBitmap.pixelsHigh

    guard
        width == whiteBitmap.pixelsWide,
        height == whiteBitmap.pixelsHigh,
        let blackData = blackBitmap.bitmapData,
        let whiteData = whiteBitmap.bitmapData
    else {
        throw NSError(
            domain: "USDZPosterRenderer",
            code: 2,
            userInfo: [NSLocalizedDescriptionKey: "Bitmap size mismatch"]
        )
    }

    guard let out = NSBitmapImageRep(
        bitmapDataPlanes: nil,
        pixelsWide: width,
        pixelsHigh: height,
        bitsPerSample: 8,
        samplesPerPixel: 4,
        hasAlpha: true,
        isPlanar: false,
        colorSpaceName: .deviceRGB,
        bytesPerRow: 0,
        bitsPerPixel: 0
    ), let outData = out.bitmapData else {
        throw NSError(
            domain: "USDZPosterRenderer",
            code: 3,
            userInfo: [NSLocalizedDescriptionKey: "Failed to create output bitmap"]
        )
    }

    let bprBlack = blackBitmap.bytesPerRow
    let bprWhite = whiteBitmap.bytesPerRow
    let bprOut = out.bytesPerRow

    for y in 0..<height {
        for x in 0..<width {
            let iBlack = y * bprBlack + x * 4
            let iWhite = y * bprWhite + x * 4
            let iOut = y * bprOut + x * 4

            let cbR = Double(blackData[iBlack]) / 255.0
            let cbG = Double(blackData[iBlack + 1]) / 255.0
            let cbB = Double(blackData[iBlack + 2]) / 255.0

            let cwR = Double(whiteData[iWhite]) / 255.0
            let cwG = Double(whiteData[iWhite + 1]) / 255.0
            let cwB = Double(whiteData[iWhite + 2]) / 255.0

            let aR = 1.0 - (cwR - cbR)
            let aG = 1.0 - (cwG - cbG)
            let aB = 1.0 - (cwB - cbB)

            var alpha = max(0.0, min(1.0, (aR + aG + aB) / 3.0))

            if alpha < 0.001 { alpha = 0.0 }

            let outR: Double
            let outG: Double
            let outB: Double

            if alpha > 0 {
                outR = max(0.0, min(1.0, cbR / alpha))
                outG = max(0.0, min(1.0, cbG / alpha))
                outB = max(0.0, min(1.0, cbB / alpha))
            } else {
                outR = 0
                outG = 0
                outB = 0
            }

            outData[iOut]     = UInt8(round(outR * 255.0))
            outData[iOut + 1] = UInt8(round(outG * 255.0))
            outData[iOut + 2] = UInt8(round(outB * 255.0))
            outData[iOut + 3] = UInt8(round(alpha * 255.0))
        }
    }

    return out
}

func renderPoster(usdzPath: String, outputPath: String, width: CGFloat = 800, height: CGFloat = 800) throws {
    let outputURL = URL(fileURLWithPath: outputPath)

    let (sceneBlack, cameraBlack) = try makeScene(usdzPath: usdzPath)
    let blackBitmap = try renderBitmap(
        scene: sceneBlack,
        cameraNode: cameraBlack,
        width: width,
        height: height,
        background: .black
    )

    let (sceneWhite, cameraWhite) = try makeScene(usdzPath: usdzPath)
    let whiteBitmap = try renderBitmap(
        scene: sceneWhite,
        cameraNode: cameraWhite,
        width: width,
        height: height,
        background: .white
    )

    let outputBitmap = try combineBlackWhiteToTransparent(
        blackBitmap: blackBitmap,
        whiteBitmap: whiteBitmap
    )

    guard let pngData = outputBitmap.representation(using: .png, properties: [:]) else {
        throw NSError(
            domain: "USDZPosterRenderer",
            code: 4,
            userInfo: [NSLocalizedDescriptionKey: "Failed to encode PNG"]
        )
    }

    try FileManager.default.createDirectory(
        at: outputURL.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )

    try pngData.write(to: outputURL)
}

let args = CommandLine.arguments
guard args.count >= 3 else {
    fputs("Usage: usdz_poster_renderer <input.usdz> <output.png>\n", stderr)
    exit(1)
}

let input = args[1]
let output = args[2]

do {
    try renderPoster(usdzPath: input, outputPath: output)
    print("Wrote PNG to: \(output)")
} catch {
    fputs("Render failed: \(error)\n", stderr)
    exit(2)
}