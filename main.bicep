targetScope = 'resourceGroup'

@description('Lowercase letters, numbers and hyphens only; start with a letter.')
@minLength(3)
@maxLength(24)
param namePrefix string = 'monitor-lab'

@description('Region supporting Application Insights and Log Analytics.')
param location string = resourceGroup().location

@description('Public HTTPS endpoint you own or have permission to test; expected HTTP 200.')
@minLength(1)
param endpointUrl string

@description('Notification recipient. Supply privately, never commit a real address.')
@secure()
param alertEmail string

var suffix = uniqueString(resourceGroup().id)
var webTestName = '${namePrefix}-availability-${suffix}'
var labTags = {
  purpose: 'portfolio-lab'
  managedBy: 'bicep'
}

resource workspace 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-logs-${suffix}'
  location: location
  tags: labTags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    workspaceCapping: {
      dailyQuotaGb: 1
    }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-app-${suffix}'
  location: location
  kind: 'web'
  tags: labTags
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: workspace.id
    IngestionMode: 'LogAnalytics'
  }
}

resource availabilityTest 'Microsoft.Insights/webtests@2022-06-15' = {
  name: webTestName
  location: location
  kind: 'standard'
  tags: {
    purpose: 'portfolio-lab'
    managedBy: 'bicep'
    'hidden-link:${appInsights.id}': 'Resource'
  }
  properties: {
    Name: webTestName
    SyntheticMonitorId: webTestName
    Description: 'Portfolio lab: HTTPS status and certificate check.'
    Enabled: true
    Kind: 'standard'
    Frequency: 300
    Timeout: 30
    RetryEnabled: true
    Locations: [
      {
        Id: 'us-va-ash-azr'
      }
      {
        Id: 'us-ca-sjc-azr'
      }
      {
        Id: 'emea-nl-ams-azr'
      }
    ]
    Request: {
      RequestUrl: endpointUrl
      HttpVerb: 'GET'
      FollowRedirects: true
      ParseDependentRequests: false
    }
    ValidationRules: {
      ExpectedHttpStatusCode: 200
      IgnoreHttpStatusCode: false
      SSLCheck: true
      SSLCertRemainingLifetimeCheck: 7
    }
  }
}

resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: '${namePrefix}-email-${suffix}'
  location: 'global'
  tags: labTags
  properties: {
    groupShortName: 'monitorlab'
    enabled: true
    emailReceivers: [
      {
        name: 'lab-email'
        emailAddress: alertEmail
        useCommonAlertSchema: true
      }
    ]
  }
}

resource availabilityAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${namePrefix}-availability-alert-${suffix}'
  location: 'global'
  tags: labTags
  properties: {
    description: 'Portfolio lab: availability test fails in at least two locations.'
    severity: 2
    enabled: true
    autoMitigate: true
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    scopes: [
      availabilityTest.id
      appInsights.id
    ]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.WebtestLocationAvailabilityCriteria'
      webTestId: availabilityTest.id
      componentId: appInsights.id
      failedLocationCount: 2
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

resource failedRequestsAlert 'Microsoft.Insights/metricAlerts@2018-03-01' = {
  name: '${namePrefix}-failed-requests-${suffix}'
  location: 'global'
  tags: labTags
  properties: {
    description: 'Portfolio lab: more than five failed application requests in five minutes.'
    severity: 2
    enabled: true
    autoMitigate: true
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    scopes: [
      appInsights.id
    ]
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'FailedRequests'
          metricNamespace: 'Microsoft.Insights/components'
          metricName: 'requests/failed'
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Count'
          skipMetricValidation: false
        }
      ]
    }
    actions: [
      {
        actionGroupId: actionGroup.id
      }
    ]
  }
}

output workspaceId string = workspace.id
output applicationInsightsId string = appInsights.id
output availabilityTestId string = availabilityTest.id
output actionGroupId string = actionGroup.id
output availabilityAlertId string = availabilityAlert.id
output failedRequestsAlertId string = failedRequestsAlert.id
