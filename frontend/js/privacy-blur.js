/**
 * CivicLoop Privacy-First Image Processing
 * 
 * On-device face and license plate blurring using TensorFlow.js
 * The original image NEVER leaves the device
 */

class PrivacyProtector {
    constructor() {
        this.faceDetector = null;
        this.isReady = false;
        this.loadModels();
    }

    async loadModels() {
        try {
            // Load BlazeFace for face detection (lightweight, runs in browser)
            await tf.setBackend('webgl');
            this.faceDetector = await blazeface.load();
            this.isReady = true;
            console.log('✅ Privacy models loaded successfully');
            return true;
        } catch (error) {
            console.error('❌ Failed to load privacy models:', error);
            return false;
        }
    }

    /**
     * Detect faces in image
     */
    async detectFaces(imageElement) {
        if (!this.isReady) {
            console.warn('Models not ready yet');
            return [];
        }

        try {
            const predictions = await this.faceDetector.estimateFaces(imageElement, false);
            return predictions;
        } catch (error) {
            console.error('Face detection error:', error);
            return [];
        }
    }

    /**
     * Simple license plate detection using pattern matching
     * For demo: detects rectangular regions with high contrast
     * In production: would use trained YOLO/MobileNet model
     */
    async detectLicensePlates(canvas, ctx) {
        const plates = [];
        
        // Get image data
        const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
        const data = imageData.data;
        
        // Simple detection: look for rectangular high-contrast regions
        // This is a placeholder - in production use trained model
        const plateRegions = this.findHighContrastRectangles(imageData);
        
        return plateRegions;
    }

    /**
     * Helper: Find rectangular regions with high contrast (plate candidates)
     */
    findHighContrastRectangles(imageData) {
        // Simplified detection for demo
        // In production: use trained ONNX model or TensorFlow.js model
        const candidates = [];
        
        const width = imageData.width;
        const height = imageData.height;
        const data = imageData.data;
        
        // Scan for horizontal lines (plate characteristic)
        // This is a very basic heuristic for demo purposes
        const step = 20;
        for (let y = step; y < height - step; y += step) {
            for (let x = step; x < width - step; x += step) {
                const brightness = this.getRegionBrightness(data, x, y, step, width);
                const contrast = this.getRegionContrast(data, x, y, step, width);
                
                // Plates usually have high contrast and moderate brightness
                if (contrast > 50 && brightness > 80 && brightness < 200) {
                    candidates.push({
                        x: x - step,
                        y: y - step,
                        width: step * 4,
                        height: step * 2
                    });
                }
            }
        }
        
        return this.mergeCandidates(candidates);
    }

    getRegionBrightness(data, x, y, size, width) {
        let sum = 0;
        let count = 0;
        
        for (let dy = 0; dy < size; dy++) {
            for (let dx = 0; dx < size; dx++) {
                const idx = ((y + dy) * width + (x + dx)) * 4;
                sum += (data[idx] + data[idx + 1] + data[idx + 2]) / 3;
                count++;
            }
        }
        
        return count > 0 ? sum / count : 0;
    }

    getRegionContrast(data, x, y, size, width) {
        const values = [];
        
        for (let dy = 0; dy < size; dy++) {
            for (let dx = 0; dx < size; dx++) {
                const idx = ((y + dy) * width + (x + dx)) * 4;
                values.push((data[idx] + data[idx + 1] + data[idx + 2]) / 3);
            }
        }
        
        if (values.length === 0) return 0;
        
        const max = Math.max(...values);
        const min = Math.min(...values);
        return max - min;
    }

    mergeCandidates(candidates) {
        // Simple merging of overlapping rectangles
        if (candidates.length === 0) return [];
        
        const merged = [];
        const used = new Set();
        
        for (let i = 0; i < candidates.length; i++) {
            if (used.has(i)) continue;
            
            let current = {...candidates[i]};
            used.add(i);
            
            // Find overlapping candidates
            for (let j = i + 1; j < candidates.length; j++) {
                if (used.has(j)) continue;
                
                if (this.rectanglesOverlap(current, candidates[j])) {
                    current = this.mergeRectangles(current, candidates[j]);
                    used.add(j);
                }
            }
            
            merged.push(current);
        }
        
        return merged;
    }

    rectanglesOverlap(r1, r2) {
        return !(r1.x + r1.width < r2.x ||
                 r2.x + r2.width < r1.x ||
                 r1.y + r1.height < r2.y ||
                 r2.y + r2.height < r1.y);
    }

    mergeRectangles(r1, r2) {
        const x = Math.min(r1.x, r2.x);
        const y = Math.min(r1.y, r2.y);
        const x2 = Math.max(r1.x + r1.width, r2.x + r2.width);
        const y2 = Math.max(r1.y + r1.height, r2.y + r2.height);
        
        return {
            x: x,
            y: y,
            width: x2 - x,
            height: y2 - y
        };
    }

    /**
     * Blur a rectangular region on canvas
     */
    blurRegion(ctx, x, y, width, height, strength = 20) {
        // Extract the region
        const imageData = ctx.getImageData(x, y, width, height);
        
        // Apply gaussian blur (simplified box blur for performance)
        const blurred = this.boxBlur(imageData, strength);
        
        // Put blurred region back
        ctx.putImageData(blurred, x, y);
    }

    /**
     * Box blur implementation (faster than gaussian for real-time)
     */
    boxBlur(imageData, radius) {
        const width = imageData.width;
        const height = imageData.height;
        const data = imageData.data;
        const output = new Uint8ClampedArray(data);
        
        // Horizontal pass
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                let r = 0, g = 0, b = 0, count = 0;
                
                for (let dx = -radius; dx <= radius; dx++) {
                    const nx = x + dx;
                    if (nx >= 0 && nx < width) {
                        const idx = (y * width + nx) * 4;
                        r += data[idx];
                        g += data[idx + 1];
                        b += data[idx + 2];
                        count++;
                    }
                }
                
                const idx = (y * width + x) * 4;
                output[idx] = r / count;
                output[idx + 1] = g / count;
                output[idx + 2] = b / count;
            }
        }
        
        // Vertical pass
        for (let x = 0; x < width; x++) {
            for (let y = 0; y < height; y++) {
                let r = 0, g = 0, b = 0, count = 0;
                
                for (let dy = -radius; dy <= radius; dy++) {
                    const ny = y + dy;
                    if (ny >= 0 && ny < height) {
                        const idx = (ny * width + x) * 4;
                        r += output[idx];
                        g += output[idx + 1];
                        b += output[idx + 2];
                        count++;
                    }
                }
                
                const idx = (y * width + x) * 4;
                data[idx] = r / count;
                data[idx + 1] = g / count;
                data[idx + 2] = b / count;
            }
        }
        
        return imageData;
    }

    /**
     * Main function: Process image and return blurred version
     * CRITICAL: Original image never leaves this function
     */
    async processImage(file) {
        return new Promise(async (resolve, reject) => {
            try {
                // Load image into memory
                const img = new Image();
                const reader = new FileReader();
                
                reader.onload = async (e) => {
                    img.onload = async () => {
                        // Create canvas for processing
                        const canvas = document.createElement('canvas');
                        canvas.width = img.width;
                        canvas.height = img.height;
                        const ctx = canvas.getContext('2d');
                        
                        // Draw original image
                        ctx.drawImage(img, 0, 0);
                        
                        // Detect and blur faces
                        const faces = await this.detectFaces(img);
                        console.log(`Found ${faces.length} face(s)`);
                        
                        for (const face of faces) {
                            const [x, y] = face.topLeft;
                            const [x2, y2] = face.bottomRight;
                            const width = x2 - x;
                            const height = y2 - y;
                            
                            // Expand box slightly for better coverage
                            const padding = 10;
                            this.blurRegion(
                                ctx,
                                Math.max(0, x - padding),
                                Math.max(0, y - padding),
                                width + padding * 2,
                                height + padding * 2,
                                15
                            );
                        }
                        
                        // Detect and blur license plates
                        const plates = await this.detectLicensePlates(canvas, ctx);
                        console.log(`Found ${plates.length} potential plate(s)`);
                        
                        for (const plate of plates) {
                            this.blurRegion(
                                ctx,
                                plate.x,
                                plate.y,
                                plate.width,
                                plate.height,
                                20
                            );
                        }
                        
                        // Convert to blob (blurred image)
                        canvas.toBlob((blob) => {
                            resolve({
                                blob: blob,
                                facesDetected: faces.length,
                                platesDetected: plates.length,
                                originalName: file.name,
                                processedSize: blob.size
                            });
                        }, 'image/jpeg', 0.92);
                        
                        // IMPORTANT: Original image in 'img' is never sent anywhere
                        // Only the blurred canvas is converted to blob
                    };
                    
                    img.src = e.target.result;
                };
                
                reader.onerror = reject;
                reader.readAsDataURL(file);
                
            } catch (error) {
                reject(error);
            }
        });
    }

    /**
     * Strip EXIF metadata from image
     */
    async stripMetadata(blob) {
        // Convert blob to array buffer
        const arrayBuffer = await blob.arrayBuffer();
        const bytes = new Uint8Array(arrayBuffer);
        
        // Find JPEG markers
        if (bytes[0] !== 0xFF || bytes[1] !== 0xD8) {
            // Not a JPEG, return as-is
            return blob;
        }
        
        // Create new JPEG without EXIF
        const output = [0xFF, 0xD8]; // SOI marker
        
        let pos = 2;
        while (pos < bytes.length - 1) {
            if (bytes[pos] !== 0xFF) break;
            
            const marker = bytes[pos + 1];
            pos += 2;
            
            // Skip APP1 (EXIF) and APP2 markers
            if (marker >= 0xE1 && marker <= 0xE2) {
                const len = (bytes[pos] << 8) + bytes[pos + 1];
                pos += len;
                continue;
            }
            
            // Copy other markers
            output.push(0xFF, marker);
            
            if (marker === 0xD9) break; // EOI
            if (marker === 0xD8) continue; // SOI
            
            // Copy segment data
            const len = (bytes[pos] << 8) + bytes[pos + 1];
            for (let i = 0; i < len; i++) {
                output.push(bytes[pos + i]);
            }
            pos += len;
        }
        
        // Return new blob without metadata
        return new Blob([new Uint8Array(output)], { type: 'image/jpeg' });
    }

    /**
     * Complete privacy pipeline: blur + strip metadata
     */
    async protectPrivacy(file) {
        console.log('🔒 Starting privacy protection...');
        console.log(`Original file: ${file.name}, ${(file.size / 1024).toFixed(2)} KB`);
        
        // Step 1: Blur faces and plates
        const processed = await this.processImage(file);
        console.log(`✅ Blurred ${processed.facesDetected} faces, ${processed.platesDetected} plates`);
        
        // Step 2: Strip EXIF metadata
        const clean = await this.stripMetadata(processed.blob);
        console.log(`✅ Metadata stripped, final size: ${(clean.size / 1024).toFixed(2)} KB`);
        
        return {
            blob: clean,
            stats: {
                facesBlurred: processed.facesDetected,
                platesBlurred: processed.platesDetected,
                originalSize: file.size,
                finalSize: clean.size,
                metadataRemoved: true
            }
        };
    }
}

// Create global instance
const privacyProtector = new PrivacyProtector();
