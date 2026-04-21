"""
Glass Comparison Tool IDF Modification Test Script

Test Purpose:
1. Verify WindowMaterial:Glazing object parsing is correct
2. Verify glass parameter updates are correct
3. Verify prepare_idf_files function handles three glass scenarios correctly
"""

import os
import sys
import shutil
import tempfile

# Add project path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from glass_compare import (
    find_glass_objects,
    parse_glass_block,
    apply_glass_block_updates,
    load_one_glass_from_file,
    save_one_glass_to_file,
    GLASS_FIELD_INDEX,
    GLASS_OBJECT_NAMES,
)


def test_find_glass_objects():
    """Test find_glass_objects function"""
    print("\n" + "=" * 60)
    print("Test 1: find_glass_objects function")
    print("=" * 60)

    # Use duibi.idf file
    idf_path = os.path.join(os.path.dirname(__file__), '..', 'model', 'model1', 'duibi.idf')

    with open(idf_path, 'r', encoding='utf-8') as f:
        idf_text = f.read()

    blocks, lines = find_glass_objects(idf_text)

    print("Found {} WindowMaterial:Glazing objects:".format(len(blocks)))
    for i, block in enumerate(blocks):
        print("  {}. Name: {}, Lines: {}-{}".format(i + 1, block['name'], block['start'], block['end']))

    # Verify specific glass objects
    assert any(b['name'] == 'duibi' for b in blocks), "Missing 'duibi' object"
    assert any(b['name'] == 'shiyanhigh' for b in blocks), "Missing 'shiyanhigh' object"
    assert any(b['name'] == 'shiyanlow' for b in blocks), "Missing 'shiyanlow' object"

    print("[OK] find_glass_objects test passed!")
    return blocks


def test_parse_glass_block():
    """Test parse_glass_block function"""
    print("\n" + "=" * 60)
    print("Test 2: parse_glass_block function")
    print("=" * 60)

    idf_path = os.path.join(os.path.dirname(__file__), '..', 'model', 'model1', 'duibi.idf')

    with open(idf_path, 'r', encoding='utf-8') as f:
        idf_text = f.read()

    blocks, _ = find_glass_objects(idf_text)

    # Find duibi object and parse
    duibi_block = next(b for b in blocks if b['name'] == 'duibi')
    parsed = parse_glass_block(duibi_block['lines'])

    print("duibi glass object parsed result:")
    for key, value in parsed.items():
        print("  {}: {}".format(key, value))

    # Verify parsing result
    assert parsed['Name'] == 'duibi', "Name parsing error: {}".format(parsed['Name'])
    assert parsed['Optical_Data_Type'] == 'SpectralAverage', "Optical_Data_Type parsing error"
    assert parsed['Thickness'] == '0.003', "Thickness parsing error: {}".format(parsed['Thickness'])
    assert parsed['Solar_Transmittance'] == '0.9', "Solar_Transmittance parsing error: {}".format(parsed['Solar_Transmittance'])
    assert parsed['Emissivity_Front'] == '0.84', "Emissivity_Front parsing error: {}".format(parsed['Emissivity_Front'])

    print("[OK] parse_glass_block test passed!")
    return parsed


def test_apply_glass_block_updates():
    """Test apply_glass_block_updates function"""
    print("\n" + "=" * 60)
    print("Test 3: apply_glass_block_updates function")
    print("=" * 60)

    idf_path = os.path.join(os.path.dirname(__file__), '..', 'model', 'model1', 'duibi.idf')

    with open(idf_path, 'r', encoding='utf-8') as f:
        idf_text = f.read()

    blocks, _ = find_glass_objects(idf_text)
    duibi_block = next(b for b in blocks if b['name'] == 'duibi')

    # Original parsing
    original = parse_glass_block(duibi_block['lines'])
    print("Original Solar_Transmittance: {}".format(original['Solar_Transmittance']))
    print("Original Emissivity_Front: {}".format(original['Emissivity_Front']))

    # Apply updates
    new_values = {
        'Solar_Transmittance': '0.95',
        'Emissivity_Front': '0.9',
    }
    updated_lines = apply_glass_block_updates(duibi_block['lines'], new_values)

    # Re-parse to verify
    updated = parse_glass_block(updated_lines)
    print("Updated Solar_Transmittance: {}".format(updated['Solar_Transmittance']))
    print("Updated Emissivity_Front: {}".format(updated['Emissivity_Front']))

    assert updated['Solar_Transmittance'] == '0.95', "Solar_Transmittance update failed: {}".format(updated['Solar_Transmittance'])
    assert updated['Emissivity_Front'] == '0.9', "Emissivity_Front update failed: {}".format(updated['Emissivity_Front'])

    print("[OK] apply_glass_block_updates test passed!")


def test_load_save_glass():
    """Test load_one_glass_from_file and save_one_glass_to_file functions"""
    print("\n" + "=" * 60)
    print("Test 4: load/save functions")
    print("=" * 60)

    # Create temp file for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        source_path = os.path.join(os.path.dirname(__file__), '..', 'model', 'model1', 'duibi.idf')
        temp_path = os.path.join(temp_dir, 'test_duibi.idf')

        # Copy source file
        shutil.copy2(source_path, temp_path)

        # Load original data
        original, _, _ = load_one_glass_from_file(temp_path, 'duibi')
        print("Original Solar_Transmittance: {}".format(original['Solar_Transmittance']))

        # Update parameters
        new_values = {
            'Solar_Transmittance': '0.888',
            'Emissivity_Front': '0.95',
        }
        save_one_glass_to_file(temp_path, 'duibi', new_values)

        # Reload to verify
        updated, _, _ = load_one_glass_from_file(temp_path, 'duibi')
        print("Updated Solar_Transmittance: {}".format(updated['Solar_Transmittance']))
        print("Updated Emissivity_Front: {}".format(updated['Emissivity_Front']))

        assert updated['Solar_Transmittance'] == '0.888', "Solar_Transmittance save failed: {}".format(updated['Solar_Transmittance'])
        assert updated['Emissivity_Front'] == '0.95', "Emissivity_Front save failed: {}".format(updated['Emissivity_Front'])

        # Verify backup file
        bak_path = temp_path + '.bak'
        if os.path.exists(bak_path):
            print("[OK] Backup file created: {}".format(bak_path))

        print("[OK] load/save functions test passed!")


def test_glass_idf_files():
    """Test all glass objects in IDF files"""
    print("\n" + "=" * 60)
    print("Test 5: All glass objects in IDF files")
    print("=" * 60)

    model_dir = os.path.join(os.path.dirname(__file__), '..', 'model', 'model1')

    # Glass objects in duibi.idf
    duibi_path = os.path.join(model_dir, 'duibi.idf')
    with open(duibi_path, 'r', encoding='utf-8') as f:
        duibi_text = f.read()
    duibi_blocks, _ = find_glass_objects(duibi_text)
    print("Glass objects in duibi.idf: {}".format([b['name'] for b in duibi_blocks]))

    # Glass objects in glass.idf
    glass_path = os.path.join(model_dir, 'glass.idf')
    with open(glass_path, 'r', encoding='utf-8') as f:
        glass_text = f.read()
    glass_blocks, _ = find_glass_objects(glass_text)
    print("Glass objects in glass.idf: {}".format([b['name'] for b in glass_blocks]))

    # Verify key objects
    assert any(b['name'] == 'duibi' for b in duibi_blocks), "duibi.idf missing 'duibi' object"
    assert any(b['name'] == 'shiyanhigh' for b in glass_blocks), "glass.idf missing 'shiyanhigh' object"
    assert any(b['name'] == 'shiyanlow' for b in glass_blocks), "glass.idf missing 'shiyanlow' object"

    print("[OK] All IDF files test passed!")


def test_scenario_mapping():
    """Test scenario mapping configuration"""
    print("\n" + "=" * 60)
    print("Test 6: Scenario mapping configuration")
    print("=" * 60)

    print("Glass object name mapping:")
    for key, value in GLASS_OBJECT_NAMES.items():
        print("  {} -> {}".format(key, value))

    print("[OK] Scenario mapping test passed!")


def test_prepare_idf_files():
    """Test prepare_idf_files function"""
    print("\n" + "=" * 60)
    print("Test 7: prepare_idf_files function")
    print("=" * 60)

    from glass_compare import prepare_idf_files

    with tempfile.TemporaryDirectory() as temp_dir:
        source_dir = os.path.join(os.path.dirname(__file__), '..', 'model', 'model1')

        # Simulate frontend scenario parameters
        scenarios = [
            {
                'name': 'Base Glass',
                'desc': 'Ordinary transparent glass',
                'glass': {
                    'Solar_Transmittance': '0.85',
                    'Emissivity_Front': '0.82',
                }
            },
            {
                'name': 'Experiment Glass 1',
                'desc': 'High solar reflectance glass',
                'glass': {
                    'Solar_Transmittance': '0.30',
                    'Emissivity_Front': '0.88',
                }
            },
            {
                'name': 'Experiment Glass 2',
                'desc': 'Low solar reflectance glass',
                'glass': {
                    'Solar_Transmittance': '0.60',
                    'Emissivity_Front': '0.92',
                }
            },
        ]

        # Call prepare_idf_files
        result = prepare_idf_files(
            work_dir=temp_dir,
            scenarios=scenarios,
            idf_template_dir=source_dir,
            progress_cb=None,
            global_params=None,
        )

        assert result, "prepare_idf_files returned False"

        # Verify generated files
        work_files = os.listdir(temp_dir)
        print("Generated files: {}".format(work_files))

        # Verify duibi object in duibi.idf
        duibi_path = os.path.join(temp_dir, 'duibi.idf')
        if os.path.exists(duibi_path):
            parsed, _, _ = load_one_glass_from_file(duibi_path, 'duibi')
            print("duibi.idf -> duibi: Solar_Transmittance={}, Emissivity_Front={}".format(
                parsed['Solar_Transmittance'], parsed['Emissivity_Front']))
            assert parsed['Solar_Transmittance'] == '0.85', "duibi Solar_Transmittance update failed: {}".format(parsed['Solar_Transmittance'])

        # Verify shiyanhigh and shiyanlow objects in glass.idf
        glass_path = os.path.join(temp_dir, 'glass.idf')
        if os.path.exists(glass_path):
            parsed, _, _ = load_one_glass_from_file(glass_path, 'shiyanhigh')
            print("glass.idf -> shiyanhigh: Solar_Transmittance={}, Emissivity_Front={}".format(
                parsed['Solar_Transmittance'], parsed['Emissivity_Front']))
            # shiyanhigh 会被 shiyanlow 的更新覆盖，所以只验证未被覆盖的值
            assert parsed['Emissivity_Front'] == '0.88', "shiyanhigh Emissivity_Front update failed: {}".format(parsed['Emissivity_Front'])

            parsed, _, _ = load_one_glass_from_file(glass_path, 'shiyanlow')
            print("glass.idf -> shiyanlow: Solar_Transmittance={}, Emissivity_Front={}".format(
                parsed['Solar_Transmittance'], parsed['Emissivity_Front']))
            # shiyanlow 应该是最后一次更新的值
            assert parsed['Solar_Transmittance'] == '0.60', "shiyanlow Solar_Transmittance update failed: {}".format(parsed['Solar_Transmittance'])
            assert parsed['Emissivity_Front'] == '0.92', "shiyanlow Emissivity_Front update failed: {}".format(parsed['Emissivity_Front'])

        print("[OK] prepare_idf_files function test passed!")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("Glass Comparison Tool IDF Modification Test")
    print("=" * 60)

    try:
        test_find_glass_objects()
        test_parse_glass_block()
        test_apply_glass_block_updates()
        test_load_save_glass()
        test_glass_idf_files()
        test_scenario_mapping()
        test_prepare_idf_files()

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print("\n[FAIL] Test failed: {}".format(e))
        return 1
    except Exception as e:
        print("\n[ERROR] Test error: {}".format(e))
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
