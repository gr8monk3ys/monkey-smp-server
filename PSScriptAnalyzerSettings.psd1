@{
    Severity     = @('Error', 'Warning')
    ExcludeRules = @(
        # These scripts are console programs for people: coloured Write-Host output is the point.
        'PSAvoidUsingWriteHost',
        # Function names read as plain verbs ("Install-Server") but they aren't cmdlets for pipelines.
        'PSUseShouldProcessForStateChangingFunctions',
        'PSUseSingularNouns',
        # Script-level parameters are read inside functions, which this rule can't see.
        'PSReviewUnusedParameter'
    )
}
