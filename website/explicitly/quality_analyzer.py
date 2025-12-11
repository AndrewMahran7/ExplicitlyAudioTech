"""
Audio quality analysis and optimization tools.

This module provides utilities to analyze and improve audio quality throughout
the Explicitly processing pipeline. It helps identify quality issues and 
provides recommendations for optimization.
"""

import json
from pathlib import Path
from typing import Dict, Any, Union, Optional, List

import numpy as np

from .utils_audio import load_audio, resample_audio, get_audio_duration


class QualityAnalyzer:
    """
    Analyzes audio quality and provides optimization recommendations.
    """
    
    def __init__(self):
        """Initialize the quality analyzer."""
        self.analysis_results = []
    
    def analyze_processing_chain(
        self,
        original_path: Union[str, Path],
        stems_dir: Union[str, Path],
        processed_vocals_path: Union[str, Path],
        final_output_path: Union[str, Path]
    ) -> Dict[str, Any]:
        """
        Analyze quality at each step of the processing pipeline.
        
        Args:
            original_path: Path to original input audio
            stems_dir: Directory containing separated stems
            processed_vocals_path: Path to censored vocals
            final_output_path: Path to final remixed output
            
        Returns:
            Complete quality analysis report
        """
        results = {
            "original_file": str(original_path),
            "analysis_timestamp": None,
            "pipeline_steps": {},
            "overall_quality": {},
            "recommendations": []
        }
        
        try:
            # Load original for reference
            original, orig_sr = load_audio(original_path, sr=None, mono=False)
            original_mono = np.mean(original, axis=0) if len(original.shape) > 1 else original
            
            # Step 1: Analyze stem separation quality
            vocals_stem_path = Path(stems_dir) / f"{Path(original_path).stem}_vocals.wav"
            instrumental_stem_path = Path(stems_dir) / f"{Path(original_path).stem}_other.wav"
            
            if vocals_stem_path.exists() and instrumental_stem_path.exists():
                stem_analysis = self._analyze_stem_quality(
                    original_mono, orig_sr, vocals_stem_path, instrumental_stem_path
                )
                results["pipeline_steps"]["stem_separation"] = stem_analysis
            
            # Step 2: Analyze vocal processing quality
            if Path(processed_vocals_path).exists():
                vocal_analysis = self._analyze_vocal_processing(
                    vocals_stem_path, processed_vocals_path
                )
                results["pipeline_steps"]["vocal_processing"] = vocal_analysis
            
            # Step 3: Analyze final remix quality
            if Path(final_output_path).exists():
                final_analysis = self._analyze_final_quality(
                    original_mono, orig_sr, final_output_path
                )
                results["pipeline_steps"]["final_remix"] = final_analysis
                results["overall_quality"] = final_analysis
            
            # Generate recommendations
            results["recommendations"] = self._generate_recommendations(results)
            
        except Exception as e:
            results["error"] = f"Analysis failed: {str(e)}"
        
        return results
    
    def _analyze_stem_quality(
        self,
        original: np.ndarray,
        orig_sr: int,
        vocals_path: Path,
        instrumental_path: Path
    ) -> Dict[str, Any]:
        """Analyze the quality of stem separation."""
        try:
            # Load separated stems
            vocals, vocal_sr = load_audio(vocals_path, sr=orig_sr, mono=True)
            instrumental, instr_sr = load_audio(instrumental_path, sr=orig_sr, mono=True)
            
            # Ensure same length
            min_len = min(len(original), len(vocals), len(instrumental))
            original = original[:min_len]
            vocals = vocals[:min_len]
            instrumental = instrumental[:min_len]
            
            # Analyze reconstruction quality
            reconstructed = vocals + instrumental
            reconstruction_error = np.mean((original - reconstructed) ** 2)
            
            if np.mean(original ** 2) > 0:
                reconstruction_snr = 10 * np.log10(np.mean(original ** 2) / reconstruction_error)
            else:
                reconstruction_snr = float('inf')
            
            # Analyze vocal isolation quality
            vocal_energy = np.mean(vocals ** 2)
            instrumental_energy = np.mean(instrumental ** 2)
            separation_ratio = vocal_energy / (vocal_energy + instrumental_energy) if (vocal_energy + instrumental_energy) > 0 else 0
            
            return {
                "reconstruction_snr_db": float(reconstruction_snr),
                "vocal_to_total_ratio": float(separation_ratio),
                "vocal_rms": float(np.sqrt(vocal_energy)),
                "instrumental_rms": float(np.sqrt(instrumental_energy)),
                "quality_rating": "Excellent" if reconstruction_snr > 15 else "Good" if reconstruction_snr > 10 else "Fair"
            }
            
        except Exception as e:
            return {"error": f"Stem analysis failed: {str(e)}"}
    
    def _analyze_vocal_processing(
        self,
        original_vocals_path: Path,
        processed_vocals_path: Path
    ) -> Dict[str, Any]:
        """Analyze quality impact of vocal processing (censoring)."""
        try:
            # Load vocal files
            original_vocals, orig_sr = load_audio(original_vocals_path, sr=None, mono=True)
            processed_vocals, proc_sr = load_audio(processed_vocals_path, sr=orig_sr, mono=True)
            
            # Analyze censoring impact
            min_len = min(len(original_vocals), len(processed_vocals))
            original_vocals = original_vocals[:min_len]
            processed_vocals = processed_vocals[:min_len]
            
            # Calculate amount of audio modified
            difference = np.abs(original_vocals - processed_vocals)
            modification_threshold = 0.01  # Threshold for detecting modifications
            modified_samples = np.sum(difference > modification_threshold)
            modification_percentage = (modified_samples / len(difference)) * 100
            
            # Calculate preserved energy
            original_energy = np.mean(original_vocals ** 2)
            processed_energy = np.mean(processed_vocals ** 2)
            energy_preservation = (processed_energy / original_energy) * 100 if original_energy > 0 else 100
            
            return {
                "modification_percentage": float(modification_percentage),
                "energy_preservation_percentage": float(energy_preservation),
                "original_rms": float(np.sqrt(original_energy)),
                "processed_rms": float(np.sqrt(processed_energy)),
                "censoring_impact": "Minimal" if modification_percentage < 10 else "Moderate" if modification_percentage < 25 else "Significant"
            }
            
        except Exception as e:
            return {"error": f"Vocal processing analysis failed: {str(e)}"}
    
    def _analyze_final_quality(
        self,
        original: np.ndarray,
        orig_sr: int,
        final_path: Path
    ) -> Dict[str, Any]:
        """Analyze final output quality compared to original."""
        try:
            # Load final output
            final, final_sr = load_audio(final_path, sr=orig_sr, mono=True)
            
            # Ensure same length for comparison
            min_len = min(len(original), len(final))
            original = original[:min_len]
            final = final[:min_len]
            
            # Calculate overall quality metrics
            mse = np.mean((original - final) ** 2)
            if mse > 0:
                overall_snr = 10 * np.log10(np.mean(original ** 2) / mse)
            else:
                overall_snr = float('inf')
            
            # Dynamic range analysis
            orig_range = np.max(original) - np.min(original)
            final_range = np.max(final) - np.min(final)
            range_preservation = (final_range / orig_range) * 100 if orig_range > 0 else 100
            
            # Energy preservation
            orig_energy = np.mean(original ** 2)
            final_energy = np.mean(final ** 2)
            energy_preservation = (final_energy / orig_energy) * 100 if orig_energy > 0 else 100
            
            # Quality rating
            if overall_snr > 20:
                quality_rating = "Excellent"
                quality_description = "Minimal perceptible difference from original"
            elif overall_snr > 15:
                quality_rating = "Very Good"
                quality_description = "Minor differences, excellent for most uses"
            elif overall_snr > 10:
                quality_rating = "Good" 
                quality_description = "Noticeable but acceptable quality"
            elif overall_snr > 5:
                quality_rating = "Fair"
                quality_description = "Some quality loss but functional"
            else:
                quality_rating = "Poor"
                quality_description = "Significant quality degradation"
            
            return {
                "overall_snr_db": float(overall_snr),
                "quality_rating": quality_rating,
                "quality_description": quality_description,
                "dynamic_range_preservation_percent": float(range_preservation),
                "energy_preservation_percent": float(energy_preservation),
                "original_duration_s": len(original) / orig_sr,
                "final_duration_s": len(final) / final_sr,
                "sample_rate_hz": int(final_sr)
            }
            
        except Exception as e:
            return {"error": f"Final quality analysis failed: {str(e)}"}
    
    def _generate_recommendations(self, analysis_results: Dict[str, Any]) -> List[str]:
        """Generate optimization recommendations based on analysis."""
        recommendations = []
        
        try:
            # Check stem separation quality
            if "stem_separation" in analysis_results["pipeline_steps"]:
                stem_data = analysis_results["pipeline_steps"]["stem_separation"]
                if "reconstruction_snr_db" in stem_data:
                    if stem_data["reconstruction_snr_db"] < 10:
                        recommendations.append("Consider using a higher quality Demucs model (htdemucs_ft or mdx_extra_q) for better stem separation")
                        recommendations.append("Try different model if vocals sound thin or instruments bleed into vocals")
            
            # Check overall quality
            if "overall_quality" in analysis_results and "overall_snr_db" in analysis_results["overall_quality"]:
                overall_snr = analysis_results["overall_quality"]["overall_snr_db"]
                
                if overall_snr < 10:
                    recommendations.append("Overall quality is below optimal - consider these improvements:")
                    recommendations.append("• Use WAV output format instead of MP3 to avoid compression artifacts")
                    recommendations.append("• Try the htdemucs_ft or htdemucs_6s model for better separation quality")
                    recommendations.append("• Ensure input audio is high quality (avoid low-bitrate MP3 inputs)")
                
                if overall_snr < 15:
                    recommendations.append("For audiophile quality, consider using the mdx_extra_q model (slower but higher quality)")
            
            # Check energy preservation
            if "overall_quality" in analysis_results and "energy_preservation_percent" in analysis_results["overall_quality"]:
                energy_pres = analysis_results["overall_quality"]["energy_preservation_percent"]
                
                if energy_pres < 80:
                    recommendations.append("Significant energy loss detected - check gain settings in remix stage")
                elif energy_pres > 120:
                    recommendations.append("Energy increased significantly - may indicate normalization issues")
            
            # Default recommendations
            if not recommendations:
                recommendations.append("Quality analysis shows good results!")
                recommendations.append("For maximum quality: use WAV output, htdemucs_ft model, and high-quality input files")
            
        except Exception as e:
            recommendations.append(f"Could not generate recommendations: {str(e)}")
        
        return recommendations
    
    def save_analysis_report(
        self,
        analysis_results: Dict[str, Any],
        output_path: Union[str, Path]
    ) -> None:
        """Save detailed analysis report to JSON file."""
        try:
            # Add timestamp
            from datetime import datetime
            analysis_results["analysis_timestamp"] = datetime.now().isoformat()
            
            # Save to file
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_results, f, indent=2, ensure_ascii=False)
            
            print(f"Quality analysis report saved: {output_path}")
            
        except Exception as e:
            raise RuntimeError(f"Failed to save analysis report: {str(e)}")


def analyze_processing_quality(
    original_path: Union[str, Path],
    stems_dir: Union[str, Path], 
    processed_vocals_path: Union[str, Path],
    final_output_path: Union[str, Path],
    report_path: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """
    Convenience function to analyze complete processing pipeline quality.
    
    Args:
        original_path: Path to original input audio
        stems_dir: Directory with separated stems
        processed_vocals_path: Path to censored vocals  
        final_output_path: Path to final output
        report_path: Optional path to save detailed report
        
    Returns:
        Quality analysis results
    """
    analyzer = QualityAnalyzer()
    results = analyzer.analyze_processing_chain(
        original_path, stems_dir, processed_vocals_path, final_output_path
    )
    
    if report_path:
        analyzer.save_analysis_report(results, report_path)
    
    # Print summary
    if "overall_quality" in results and "quality_rating" in results["overall_quality"]:
        rating = results["overall_quality"]["quality_rating"]
        snr = results["overall_quality"].get("overall_snr_db", 0)
        print(f"🎵 Overall Quality: {rating} (SNR: {snr:.1f} dB)")
        
        if "recommendations" in results:
            print("💡 Recommendations:")
            for rec in results["recommendations"]:
                print(f"   {rec}")
    
    return results