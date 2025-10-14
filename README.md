<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Radiative Cooling/Heating Calculator</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.0/es5/tex-mml-chtml.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.8;
            color: #2c3e50;
            background: linear-gradient(135deg, #f5f7fa 0%, #e8ecf1 100%);
            padding: 0;
        }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
            background: white;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
        }

        header {
            text-align: center;
            padding: 60px 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            margin: -40px -20px 40px -20px;
            border-radius: 0 0 30px 30px;
        }

        h1 {
            font-size: 2.8em;
            margin-bottom: 15px;
            font-weight: 700;
            letter-spacing: -1px;
        }

        .subtitle {
            font-size: 1.2em;
            opacity: 0.95;
            font-weight: 300;
        }

        h2 {
            color: #667eea;
            font-size: 2em;
            margin: 50px 0 25px 0;
            padding-bottom: 15px;
            border-bottom: 3px solid #e8ecf1;
        }

        h3 {
            color: #764ba2;
            font-size: 1.5em;
            margin: 35px 0 20px 0;
        }

        .features {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 25px;
            margin: 30px 0;
        }

        .feature-card {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            padding: 30px;
            border-radius: 15px;
            border-left: 4px solid #667eea;
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }

        .feature-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(102, 126, 234, 0.2);
        }

        .feature-card h3 {
            color: #667eea;
            font-size: 1.3em;
            margin: 0 0 15px 0;
        }

        .formula-box {
            background: #f8f9fa;
            padding: 25px;
            border-radius: 10px;
            margin: 25px 0;
            border-left: 4px solid #764ba2;
            overflow-x: auto;
        }

        .principle-section {
            background: linear-gradient(135deg, #fef5e7 0%, #fdebd0 100%);
            padding: 30px;
            border-radius: 15px;
            margin: 30px 0;
            border: 2px solid #f8c471;
        }

        code {
            background: #e9ecef;
            padding: 3px 8px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
            color: #e74c3c;
        }

        pre {
            background: #2c3e50;
            color: #ecf0f1;
            padding: 20px;
            border-radius: 10px;
            overflow-x: auto;
            margin: 20px 0;
        }

        .badge {
            display: inline-block;
            padding: 5px 12px;
            background: #667eea;
            color: white;
            border-radius: 20px;
            font-size: 0.85em;
            margin: 5px 5px 5px 0;
        }

        .info-box {
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 20px;
            margin: 25px 0;
            border-radius: 8px;
        }

        .warning-box {
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 20px;
            margin: 25px 0;
            border-radius: 8px;
        }

        ul, ol {
            margin: 15px 0 15px 30px;
        }

        li {
            margin: 10px 0;
        }

        a {
            color: #667eea;
            text-decoration: none;
            transition: color 0.3s ease;
        }

        a:hover {
            color: #764ba2;
            text-decoration: underline;
        }

        .contact-section {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px;
            border-radius: 15px;
            margin-top: 50px;
            text-align: center;
        }

        .contact-section h2 {
            color: white;
            border-bottom: 3px solid rgba(255,255,255,0.3);
        }

        table {
            width: 100%;
            border-collapse: collapse;
            margin: 25px 0;
            background: white;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
        }

        th, td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid #e8ecf1;
        }

        th {
            background: #667eea;
            color: white;
            font-weight: 600;
        }

        tr:hover {
            background: #f8f9fa;
        }

        .icon {
            font-size: 2em;
            margin-bottom: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🌡️ Radiative Cooling/Heating Calculator</h1>
            <p class="subtitle">Advanced Computational Tool for Thermal Radiation Analysis</p>
            <div style="margin-top: 20px;">
                <span class="badge">Python</span>
                <span class="badge">PyQt5</span>
                <span class="badge">Thermal Physics</span>
                <span class="badge">Computational</span>
            </div>
        </header>

        <section>
            <h2>📖 Overview</h2>
            <p>
                The Radiative Cooling/Heating Calculator is a sophisticated computational tool designed for researchers and engineers 
                working in thermal management, building energy efficiency, and advanced material science. This software provides 
                accurate calculations of radiative heat transfer, incorporating solar radiation, atmospheric effects, and material 
                optical properties.
            </p>
        </section>

        <section>
            <h2>✨ Key Features</h2>
            <div class="features">
                <div class="feature-card">
                    <div class="icon">❄️</div>
                    <h3>Radiative Cooling</h3>
                    <p>Calculate cooling power using atmospheric transparency window (8-13 μm) with precise spectral integration</p>
                </div>
                <div class="feature-card">
                    <div class="icon">🔥</div>
                    <h3>Radiative Heating</h3>
                    <p>Compute heating power considering solar absorption and atmospheric downward radiation</p>
                </div>
                <div class="feature-card">
                    <div class="icon">🗺️</div>
                    <h3>Energy Mapping</h3>
                    <p>Generate energy efficiency maps for various geographical and climate conditions</p>
                </div>
                <div class="feature-card">
                    <div class="icon">💨</div>
                    <h3>Convection Analysis</h3>
                    <p>Wind speed effects on cooling efficiency with Reynolds and Nusselt number calculations</p>
                </div>
                <div class="feature-card">
                    <div class="icon">📊</div>
                    <h3>Data Visualization</h3>
                    <p>Interactive plots and contour maps for comprehensive thermal analysis</p>
                </div>
                <div class="feature-card">
                    <div class="icon">🔧</div>
                    <h3>Material Properties</h3>
                    <p>Customizable spectral emissivity and reflectance for various materials</p>
                </div>
            </div>
        </section>

        <section>
            <h2>🔬 Physical Principles</h2>
            
            <div class="principle-section">
                <h3>1. Planck's Law of Blackbody Radiation</h3>
                <p>The spectral radiance of a blackbody at temperature T is given by:</p>
                <div class="formula-box">
                    \[
                    I_{BB}(\lambda, T) = \frac{2hc^2}{\lambda^5} \frac{1}{e^{\frac{hc}{\lambda k_B T}} - 1}
                    \]
                </div>
                <p>Where:</p>
                <ul>
                    <li>\(h = 6.626 \times 10^{-34}\) J·s (Planck's constant)</li>
                    <li>\(c = 2.998 \times 10^8\) m/s (speed of light)</li>
                    <li>\(k_B = 1.381 \times 10^{-23}\) J/K (Boltzmann constant)</li>
                    <li>\(\lambda\) = wavelength (m)</li>
                    <li>\(T\) = temperature (K)</li>
                </ul>
            </div>

            <div class="principle-section">
                <h3>2. Net Radiative Cooling Power</h3>
                <p>The net cooling power of a radiative cooler is calculated as:</p>
                <div class="formula-box">
                    \[
                    P_{cool}(T) = P_{rad}(T) - P_{atm}(T_{amb}) - P_{solar} - P_{conv}
                    \]
                </div>
                <p>Where each component is:</p>
                
                <h4>a) Radiative Power (Upward)</h4>
                <div class="formula-box">
                    \[
                    P_{rad}(T) = \int_0^{2\pi} d\phi \int_0^{\pi/2} \cos\theta \sin\theta \, d\theta \int_{\lambda_1}^{\lambda_2} \varepsilon(\lambda, \theta) I_{BB}(\lambda, T) \, d\lambda
                    \]
                </div>

                <h4>b) Atmospheric Radiation (Downward)</h4>
                <div class="formula-box">
                    \[
                    P_{atm}(T_{amb}) = \int_0^{2\pi} d\phi \int_0^{\pi/2} \cos\theta \sin\theta \, d\theta \int_{\lambda_1}^{\lambda_2} \varepsilon(\lambda, \theta) \varepsilon_{atm}(\lambda, \theta) I_{BB}(\lambda, T_{amb}) \, d\lambda
                    \]
                </div>
                <p>Where atmospheric emissivity is derived from transmittance:</p>
                <div class="formula-box">
                    \[
                    \varepsilon_{atm}(\lambda, \theta) = 1 - \tau(\lambda)^{\sec\theta}
                    \]
                </div>

                <h4>c) Solar Absorption</h4>
                <div class="formula-box">
                    \[
                    P_{solar} = \alpha_s \cdot I_{solar}
                    \]
                </div>
                <p>Where \(\alpha_s\) is the solar absorptance:</p>
                <div class="formula-box">
                    \[
                    \alpha_s = 1 - R_{sol} = 1 - \frac{\int_{0.3}^{2.5} R(\lambda) I_{AM1.5}(\lambda) d\lambda}{\int_{0.3}^{2.5} I_{AM1.5}(\lambda) d\lambda}
                    \]
                </div>

                <h4>d) Convective Heat Transfer</h4>
                <div class="formula-box">
                    \[
                    P_{conv} = h_c \cdot (T - T_{amb})
                    \]
                </div>
            </div>

            <div class="principle-section">
                <h3>3. Convection Coefficient Calculation</h3>
                <p>The convection coefficient combines natural and forced convection:</p>
                
                <h4>Natural Convection (Rayleigh Number)</h4>
                <div class="formula-box">
                    \[
                    Ra = \frac{g\beta \Delta T L^3}{\nu \alpha} = Gr \cdot Pr
                    \]
                </div>
                <div class="formula-box">
                    \[
                    Nu_{nat} = \begin{cases}
                    0.54 \cdot Ra^{1/4} & Ra < 10^7 \text{ (laminar)} \\
                    0.15 \cdot Ra^{1/3} & Ra > 10^7 \text{ (turbulent)}
                    \end{cases}
                    \]
                </div>

                <h4>Forced Convection (Reynolds Number)</h4>
                <div class="formula-box">
                    \[
                    Re = \frac{v L}{\nu}
                    \]
                </div>
                <div class="formula-box">
                    \[
                    Nu_{forced} = \begin{cases}
                    0.664 \cdot Re^{1/2} \cdot Pr^{1/3} & Re < 5 \times 10^5 \text{ (laminar)} \\
                    0.037 \cdot Re^{4/5} \cdot Pr^{1/3} & Re > 5 \times 10^5 \text{ (turbulent)}
                    \end{cases}
                    \]
                </div>

                <h4>Combined Convection</h4>
                <div class="formula-box">
                    \[
                    h_c = (h_{nat}^n + h_{forced}^n)^{1/n}, \quad n = 3
                    \]
                </div>
            </div>

            <div class="principle-section">
                <h3>4. Average Emissivity</h3>
                <p>Temperature-weighted average emissivity:</p>
                <div class="formula-box">
                    \[
                    \bar{\varepsilon}(T) = \frac{\int_{\lambda_1}^{\lambda_2} \varepsilon(\lambda) I_{BB}(\lambda, T) d\lambda}{\int_{\lambda_1}^{\lambda_2} I_{BB}(\lambda, T) d\lambda}
                    \]
                </div>
            </div>
        </section>

        <section>
            <h2>🖥️ Computational Features</h2>
            
            <h3>Spectral Integration</h3>
            <div class="info-box">
                <strong>Angular Integration:</strong> The software uses adaptive quadrature with 100+ angular points from 0° to 90° 
                to accurately capture the hemispherical integration of radiation.
            </div>
            
            <div class="info-box">
                <strong>Wavelength Integration:</strong> Trapezoidal integration over user-defined spectral ranges with automatic 
                interpolation of material properties.
            </div>

            <h3>Material Property Processing</h3>
            <ul>
                <li>Automatic wavelength unit conversion (nm to μm)</li>
                <li>Spectral data interpolation using scipy's interp1d</li>
                <li>Multi-encoding file support (UTF-8, GBK, GB2312)</li>
                <li>Validation of spectral data ranges and consistency</li>
            </ul>

            <h3>Numerical Methods</h3>
            <table>
                <tr>
                    <th>Method</th>
                    <th>Application</th>
                    <th>Accuracy</th>
                </tr>
                <tr>
                    <td>Trapezoidal Rule</td>
                    <td>Spectral integration</td>
                    <td>O(Δλ²)</td>
                </tr>
                <tr>
                    <td>Brent's Method</td>
                    <td>Root finding for equilibrium temperature</td>
                    <td>Machine precision</td>
                </tr>
                <tr>
                    <td>Linear Interpolation</td>
                    <td>Spectral data resampling</td>
                    <td>O(Δλ)</td>
                </tr>
                <tr>
                    <td>Minimize Scalar</td>
                    <td>Optimization for approximate solutions</td>
                    <td>Configurable tolerance</td>
                </tr>
            </table>
        </section>

        <section>
            <h2>⚙️ Installation</h2>
            
            <h3>Requirements</h3>
            <pre><code>Python >= 3.7
PyQt5 >= 5.15
numpy >= 1.19
scipy >= 1.5
pandas >= 1.1
matplotlib >= 3.3
openpyxl >= 3.0</code></pre>

            <h3>Installation Steps</h3>
            <div class="warning-box">
                <strong>Note:</strong> Ensure all required data files are present in the <code>default/</code> directory before running.
            </div>

            <pre><code># Clone the repository
git clone https://github.com/yourusername/radiation-calculator.git
cd radiation-calculator

# Install dependencies
pip install -r requirements.txt

# Run the application
python main.py</code></pre>
        </section>

        <section>
            <h2>📁 Required Data Files</h2>
            <table>
                <tr>
                    <th>File</th>
                    <th>Description</th>
                    <th>Format</th>
                </tr>
                <tr>
                    <td>config.ini</td>
                    <td>Configuration parameters and physical constants</td>
                    <td>INI</td>
                </tr>
                <tr>
                    <td>AM1.5.dll</td>
                    <td>Standard solar spectrum (AM1.5G)</td>
                    <td>Excel</td>
                </tr>
                <tr>
                    <td>wavelength.csv</td>
                    <td>Wavelength grid for calculations</td>
                    <td>CSV</td>
                </tr>
                <tr>
                    <td>reflectance.txt</td>
                    <td>Material spectral reflectance (0.3-2.5 μm)</td>
                    <td>TXT (2 columns)</td>
                </tr>
                <tr>
                    <td>emissivity.txt</td>
                    <td>Material spectral emissivity (8-13 μm)</td>
                    <td>TXT (2 columns)</td>
                </tr>
                <tr>
                    <td>1.dll / 2.dll</td>
                    <td>Atmospheric transmittance (clear/cloudy)</td>
                    <td>Excel</td>
                </tr>
            </table>
        </section>

        <section>
            <h2>🎯 Usage Examples</h2>
            
            <h3>1. Basic Cooling Power Calculation</h3>
            <ol>
                <li>Select material reflectance file (visible to near-IR range)</li>
                <li>Select material emissivity file (mid-IR atmospheric window)</li>
                <li>Choose atmospheric conditions (clear sky or cloudy)</li>
                <li>Click "Radiation Cooling Power" to calculate</li>
                <li>View results and export data as needed</li>
            </ol>

            <h3>2. Energy Map Generation</h3>
            <ol>
                <li>Prepare material property files</li>
                <li>Click "Energy Map Calculation"</li>
                <li>Obtain weighted emissivity and solar reflectance</li>
                <li>Use parameters for regional energy modeling</li>
            </ol>

            <h3>3. Wind Speed Analysis</h3>
            <ol>
                <li>Load all required material files</li>
                <li>Select "Wind Speed & Cooling Efficiency"</li>
                <li>Input solar irradiance value (W/m²)</li>
                <li>Generate 2D contour maps showing cooling power vs. wind speed and atmospheric emissivity</li>
            </ol>
        </section>

        <section>
            <h2>📊 Output Parameters</h2>
            
            <div class="features">
                <div class="feature-card">
                    <h3>Cooling Power</h3>
                    <p>Net radiative cooling power (W/m²) at ambient temperature</p>
                </div>
                <div class="feature-card">
                    <h3>Heating Power</h3>
                    <p>Net radiative heating power (W/m²) including solar gains</p>
                </div>
                <div class="feature-card">
                    <h3>Solar Absorptance</h3>
                    <p>Weighted solar absorptance (0.3-2.5 μm)</p>
                </div>
                <div class="feature-card">
                    <h3>IR Emissivity</h3>
                    <p>Temperature-weighted emissivity (8-13 μm)</p>
                </div>
                <div class="feature-card">
                    <h3>Convection Coefficient</h3>
                    <p>h_c (W/m²·K) as function of wind speed and ΔT</p>
                </div>
                <div class="feature-card">
                    <h3>Cloud Maps</h3>
                    <p>2D parametric plots for design optimization</p>
                </div>
            </div>
        </section>

        <section>
            <h2>🔧 Advanced Features</h2>
            
            <h3>Configuration Editor</h3>
            <p>Built-in editor for modifying calculation parameters:</p>
            <ul>
                <li>Physical constants (h, c, k_B)</li>
                <li>Temperature ranges for calculations</li>
                <li>Wavelength integration bounds</li>
                <li>Convection coefficient values</li>
                <li>Solar irradiance intensity</li>
            </ul>

            <h3>File Converter Tool</h3>
            <p>Excel to TXT converter for spectral data preparation:</p>
            <ul>
                <li>Extracts first two columns automatically</li>
                <li>Handles multiple encoding formats</li>
                <li>Validates data structure</li>
            </ul>

            <h3>Multi-language Support</h3>
            <p>Interface available in Chinese and English with dynamic switching</p>
        </section>

        <section>
            <h2>📈 Validation & Accuracy</h2>
            
            <div class="info-box">
                <h3>Key Considerations:</h3>
                <ul>
                    <li><strong>Spectral Resolution:</strong> Calculations use user-provided spectral data. Higher resolution improves accuracy.</li>
                    <li><strong>Angular Integration:</strong> 100+ points ensure convergence for hemispherical integration (tested error < 0.5%)</li>
                    <li><strong>Temperature Range:</strong> Valid from -100°C to +100°C for typical materials</li>
                    <li><strong>Wavelength Coverage:</strong> Solar (0.3-2.5 μm) and IR (8-13 μm) windows are critical</li>
                </ul>
            </div>

            <div class="warning-box">
                <strong>Important:</strong> Results are most accurate when:
                <ul>
                    <li>Material properties are measured with calibrated instruments</li>
                    <li>Atmospheric conditions match standard profiles</li>
                    <li>Surface is diffuse (Lambertian assumption)</li>
                    <li>Steady-state conditions are assumed</li>
                </ul>
            </div>
        </section>

        <section>
            <h2>📚 References</h2>
            <ol>
                <li>Raman, A. P., et al. "Passive radiative cooling below ambient air temperature under direct sunlight." <em>Nature</em> 515.7528 (2014): 540-544.</li>
                <li>Zhao, Dongliang, et al. "Radiative sky cooling: Fundamental principles, materials, and applications." <em>Applied Physics Reviews</em> 6.2 (2019): 021306.</li>
                <li>Incropera, F. P., et al. <em>Fundamentals of Heat and Mass Transfer</em>. 7th ed. Wiley, 2011.</li>
                <li>Bergman, T. L., et al. <em>Introduction to Heat Transfer</em>. 6th ed. Wiley, 2011.</li>
                <li>Siegel, R., and J. R. Howell. <em>Thermal Radiation Heat Transfer</em>. 5th ed. CRC Press, 2010.</li>
            </ol>
        </section>

        <div class="contact-section">
            <h2>📬 Contact & Citation</h2>
            <p style="margin-top: 20px; font-size: 1.1em;">
                If you use this tool in your research, please cite our work and contact the author for collaboration opportunities.
            </p>
            <p style="margin-top: 15px;">
                <strong>QQ Group:</strong> 767753318<br>
                <strong>WeChat:</strong> cuity_<br>
                <strong>Repository:</strong> <a href="https://gitee.com/cuity1999/Radiation-cooling-and-heating-calculation" style="color: white; text-decoration: underline;">Gitee</a>
            </p>
            <p style="margin-top: 25px; opacity: 0.9;">
                This software is provided free for academic and research purposes. Commercial use requires permission.
            </p>
        </div>

        <footer style="text-align: center; padding: 30px 0; color: #7f8c8d; margin-top: 50px; border-top: 2px solid #e8ecf1;">
            <p>© 2024 Radiative Cooling/Heating Calculator | Version 3.5</p>
            <p style="margin-top: 10px; font-size: 0.9em;">Made with ❤️ for the thermal sciences community</p>
        </footer>
    </div>
</body>
</html>
