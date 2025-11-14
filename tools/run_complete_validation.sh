#!/bin/bash
#
# Complete Validation Pipeline for International Basketball Leagues
#
# This script runs the full validation workflow:
# 1. Quick structure validation
# 2. Import validation
# 3. Game index validation (if available)
# 4. Data fetching tests (if game indexes are valid)
# 5. Comprehensive reporting
#
# Usage:
#   bash tools/run_complete_validation.sh               # All leagues
#   bash tools/run_complete_validation.sh BCL           # Single league
#   bash tools/run_complete_validation.sh BCL BAL ABA   # Multiple leagues
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default leagues
if [ $# -eq 0 ]; then
    LEAGUES=("BCL" "BAL" "ABA" "LKL" "ACB" "LNB")
else
    LEAGUES=("$@")
fi

# Results directory
RESULTS_DIR="validation_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

echo "========================================================================"
echo "INTERNATIONAL BASKETBALL LEAGUES - COMPLETE VALIDATION PIPELINE"
echo "========================================================================"
echo "Leagues: ${LEAGUES[*]}"
echo "Results: $RESULTS_DIR"
echo "========================================================================"
echo ""

# Step 1: Quick Structure Validation
echo "========================================================================"
echo "STEP 1: Quick Structure Validation (no imports)"
echo "========================================================================"

python tools/quick_validate_leagues.py \
    --export "$RESULTS_DIR/quick_validation.json" | tee "$RESULTS_DIR/01_quick_validation.log"

QUICK_EXIT_CODE=$?

if [ $QUICK_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ Quick validation passed${NC}"
else
    echo -e "${YELLOW}⚠️  Quick validation found issues (see log)${NC}"
fi

echo ""

# Step 2: Import Validation
echo "========================================================================"
echo "STEP 2: Import Validation (test all modules load)"
echo "========================================================================"

python tools/validate_international_data.py \
    --quick \
    --export "$RESULTS_DIR/import_validation.json" | tee "$RESULTS_DIR/02_import_validation.log"

IMPORT_EXIT_CODE=$?

if [ $IMPORT_EXIT_CODE -ne 0 ]; then
    echo -e "${RED}❌ Import validation failed - cannot proceed${NC}"
    echo "See $RESULTS_DIR/02_import_validation.log for details"
    exit 1
fi

echo -e "${GREEN}✅ All imports successful${NC}"
echo ""

# Step 3: Game Index Validation (FIBA leagues only)
echo "========================================================================"
echo "STEP 3: Game Index Validation (FIBA leagues)"
echo "========================================================================"

for league in "${LEAGUES[@]}"; do
    case $league in
        BCL|BAL|ABA|LKL)
            echo "Validating $league game index..."

            python tools/fiba_game_index_validator.py \
                --league "$league" \
                --season 2023-24 \
                --report > "$RESULTS_DIR/03_game_index_${league}.log" 2>&1

            if grep -q "Index ready for use" "$RESULTS_DIR/03_game_index_${league}.log"; then
                echo -e "${GREEN}✅ $league game index valid${NC}"
            else
                echo -e "${YELLOW}⚠️  $league game index has issues (placeholder data?)${NC}"
            fi
            ;;
        *)
            echo "Skipping $league (not FIBA league)"
            ;;
    esac
done

echo ""

# Step 4: Complete Flow Testing (per league)
echo "========================================================================"
echo "STEP 4: Complete Flow Testing (data fetching)"
echo "========================================================================"
echo "NOTE: This step requires valid game indexes and network access"
echo "Skipping for now (run manually when ready)"
echo ""

# Uncomment when game indexes have real data:
# for league in "${LEAGUES[@]}"; do
#     echo "Testing $league complete flow..."
#
#     python tools/test_league_complete_flow.py \
#         --league "$league" \
#         --season 2023-24 \
#         --quick \
#         --export "$RESULTS_DIR/04_flow_test_${league}.json" \
#         > "$RESULTS_DIR/04_flow_test_${league}.log" 2>&1
#
#     FLOW_EXIT_CODE=$?
#
#     if [ $FLOW_EXIT_CODE -eq 0 ]; then
#         echo -e "${GREEN}✅ $league flow test passed${NC}"
#     else
#         echo -e "${RED}❌ $league flow test failed${NC}"
#     fi
# done

# Step 5: Comprehensive Validation
echo "========================================================================"
echo "STEP 5: Comprehensive Validation (full test suite)"
echo "========================================================================"

# Only run if imports passed
if [ $IMPORT_EXIT_CODE -eq 0 ]; then
    python tools/validate_international_data.py \
        --comprehensive \
        --export "$RESULTS_DIR/05_comprehensive_validation.json" \
        > "$RESULTS_DIR/05_comprehensive_validation.log" 2>&1

    COMPREHENSIVE_EXIT_CODE=$?

    if [ $COMPREHENSIVE_EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✅ Comprehensive validation passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Comprehensive validation found issues${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Skipping comprehensive validation (imports failed)${NC}"
fi

echo ""

# Step 6: Generate Summary Report
echo "========================================================================"
echo "STEP 6: Generating Summary Report"
echo "========================================================================"

SUMMARY_FILE="$RESULTS_DIR/SUMMARY.md"

cat > "$SUMMARY_FILE" <<EOF
# Validation Summary

**Date**: $(date +"%Y-%m-%d %H:%M:%S")
**Leagues Tested**: ${LEAGUES[*]}
**Results Directory**: $RESULTS_DIR

---

## Quick Validation

EOF

if [ $QUICK_EXIT_CODE -eq 0 ]; then
    echo "✅ **PASSED** - All code structure checks passed" >> "$SUMMARY_FILE"
else
    echo "⚠️  **WARNINGS** - See \`01_quick_validation.log\`" >> "$SUMMARY_FILE"
fi

cat >> "$SUMMARY_FILE" <<EOF

---

## Import Validation

EOF

if [ $IMPORT_EXIT_CODE -eq 0 ]; then
    echo "✅ **PASSED** - All modules import successfully" >> "$SUMMARY_FILE"
else
    echo "❌ **FAILED** - Import errors found (see \`02_import_validation.log\`)" >> "$SUMMARY_FILE"
fi

cat >> "$SUMMARY_FILE" <<EOF

---

## Game Index Validation

| League | Status | Details |
|--------|--------|---------|
EOF

for league in "${LEAGUES[@]}"; do
    case $league in
        BCL|BAL|ABA|LKL)
            LOG_FILE="$RESULTS_DIR/03_game_index_${league}.log"
            if [ -f "$LOG_FILE" ]; then
                if grep -q "Index ready for use" "$LOG_FILE"; then
                    echo "| $league | ✅ Valid | Ready for use |" >> "$SUMMARY_FILE"
                else
                    echo "| $league | ⚠️  Issues | See log file |" >> "$SUMMARY_FILE"
                fi
            else
                echo "| $league | ❓ Unknown | Not validated |" >> "$SUMMARY_FILE"
            fi
            ;;
        *)
            echo "| $league | N/A | Not FIBA league |" >> "$SUMMARY_FILE"
            ;;
    esac
done

cat >> "$SUMMARY_FILE" <<EOF

---

## Next Steps

### If All Validations Passed ✅

1. **Collect Real Game IDs** (for FIBA leagues with placeholder data):
   \`\`\`bash
   python tools/fiba/collect_game_ids.py --league BCL --season 2023-24 --interactive
   \`\`\`

2. **Test Complete Data Flow**:
   \`\`\`bash
   python tools/test_league_complete_flow.py --league BCL --season 2023-24
   \`\`\`

3. **Add to Production Pipeline**

### If Validations Failed ❌

1. **Check Import Errors**: Review \`02_import_validation.log\`
2. **Fix Code Issues**: Address any import or syntax errors
3. **Re-run Validation**: \`bash tools/run_complete_validation.sh\`

---

## Files Generated

EOF

for file in "$RESULTS_DIR"/*; do
    filename=$(basename "$file")
    filesize=$(du -h "$file" | cut -f1)
    echo "- \`$filename\` ($filesize)" >> "$SUMMARY_FILE"
done

cat >> "$SUMMARY_FILE" <<EOF

---

## Reference Documentation

- **Testing Guide**: docs/TESTING_VALIDATION_GUIDE.md
- **Changes Summary**: docs/SESSION_CHANGES_SUMMARY.md
- **Validation Details**: VALIDATION_SUMMARY.md
- **League Examples**: docs/INTERNATIONAL_LEAGUES_EXAMPLES.md

EOF

echo -e "${GREEN}✅ Summary report generated: $SUMMARY_FILE${NC}"
echo ""

# Display summary
echo "========================================================================"
echo "VALIDATION PIPELINE COMPLETE"
echo "========================================================================"
cat "$SUMMARY_FILE"
echo ""
echo "========================================================================"
echo "Full results saved to: $RESULTS_DIR"
echo "========================================================================"
