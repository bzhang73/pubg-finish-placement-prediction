import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import itertools
import gc
import os
import sys

from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import minmax_scale
import lightgbm as lgb



pd.options.display.float_format = '{:,.3f}'.format


def toTapleList(list1,list2):
    return list(itertools.product(list1,list2))

#save memory function
#https://www.kaggle.com/gemartin/load-data-reduce-memory-usage
def reduce_mem_usage(df):
    """ iterate through all the columns of a dataframe and modify the data type
        to reduce memory usage.
    """
    start_mem = df.memory_usage().sum() / 1024**2
    
    for col in df.columns:
        col_type = df[col].dtype
        
        if col_type != object:
            c_min = df[col].min()
            c_max = df[col].max()
            if str(col_type)[:3] == 'int':
                if c_min > np.iinfo(np.int8).min and c_max < np.iinfo(np.int8).max:
                    df[col] = df[col].astype(np.int8)
                elif c_min > np.iinfo(np.int16).min and c_max < np.iinfo(np.int16).max:
                    df[col] = df[col].astype(np.int16)
                elif c_min > np.iinfo(np.int32).min and c_max < np.iinfo(np.int32).max:
                    df[col] = df[col].astype(np.int32)
                elif c_min > np.iinfo(np.int64).min and c_max < np.iinfo(np.int64).max:
                    df[col] = df[col].astype(np.int64)
            else:
                #if c_min > np.finfo(np.float16).min and c_max < np.finfo(np.float16).max:
                #    df[col] = df[col].astype(np.float16)
                #el
                if c_min > np.finfo(np.float32).min and c_max < np.finfo(np.float32).max:
                    df[col] = df[col].astype(np.float32)
                else:
                    df[col] = df[col].astype(np.float64)
                #else:
                    #df[col] = df[col].astype('category')

    end_mem = df.memory_usage().sum() / 1024**2
    print('Memory usage of dataframe is {:.2f} MB --> {:.2f} MB (Decreased by {:.1f}%)'.format(
                                                                                               start_mem, end_mem, 100 * (start_mem - end_mem) / start_mem))
    return df


#load data
train = pd.read_csv('input/train_V2.csv')
train = reduce_mem_usage(train)

test = pd.read_csv('input/test_V2.csv')
test = reduce_mem_usage(test)
print(train.shape, test.shape)

print()
#print the train info
train.info()

print()
null_cnt = train.isnull().sum().sort_values()
print('null count:', null_cnt[null_cnt>0])
#delet null use dropna
train.dropna(inplace=True)

print()
print(train.describe(include=np.number).drop('count').T)


print()
#Data Analysis

#Match id, groupid, matchid
for c in ['Id','groupId','matchId']:
    print(f'unique [{c}] count:',train[c].nunique())

print()
#For pubg there are three module, solo, duo and squad in the game
#matchType
fig, ax=plt.subplots(1,2,figsize=(12,4))
#solo: solo, solo-fpp, normal-solo, normal-solo-fpp
#duo: duo, duo-fpp, normal-duo, normal-duo-fpp, crashfpp, crashtpp
#squad: squad, squad-fpp, normal-squad, normal-squad-fpp, flarefpp, flaretpp
train.groupby('matchId')['matchType'].first().value_counts().plot.bar(ax=ax[0])
mapper = lambda x: 'solo' if ('solo' in x) else 'duo' if ('duo' in x) or ('crash' in x) else 'squad'
train['matchType'] = train['matchType'].apply(mapper)
train.groupby('matchId')['matchType'].first().value_counts().plot.bar(ax=ax[1])
plt.pause(15)


print()
#print the number of the maxplace groups
for q in ['numGroups == maxPlace', 'numGroups != maxPlace']:
    print(q, ':', len(train.query(q)))

print()
#numGroups, maxPlace, group_in_match
cols = ['numGroups','maxPlace']
desc1 = train.groupby('matchType')[cols].describe()[toTapleList(cols,['min','mean','max'])]
group = train.groupby(['matchType', 'matchId', 'groupId']).count().groupby(['matchType','matchId']).size().to_frame('groups_in_match')
desc2 = group.groupby('matchType').describe()[toTapleList(['groups_in_match'],['min','mean','max'])]
group_res = pd.concat([desc1,desc2],axis=1)
print(group_res)


print()
#number players in match
#each server have 100 player
#solo have max 100 players as 100 group
#duo have max 100 players as 50 group
#squad have max 100 player each group have 4 people as 25 groups
match = train.groupby(['matchType','matchId']).size().to_frame('players_in_match')
group = train.groupby(['matchType','matchId','groupId']).size().to_frame('players_in_group')
player_res = pd.concat([match.groupby('matchType').describe()[toTapleList(['players_in_match'],['min','mean','max'])],
                        group.groupby('matchType').describe()[toTapleList(['players_in_group'],['min','mean','max'])]],axis=1)
print(player_res)


print()
#for group more than maxsize
print(group['players_in_group'].nlargest(5))
del match,group


print()
#example matchId=='41a634f62f86b7', groupId=='128b07271aa012'
subset = train[train['matchId']=='41a634f62f86b7']
sub_group = subset[subset['groupId'] == '128b07271aa012']

print('matchId==\'41a634f62f86b7\' & groupId==\'128b07271aa012\'')
print('-'*50)
print('players:',len(subset))
print('groups:',subset['groupId'].nunique())
print('maxPlace:',subset['maxPlace'].nunique())
print('-'*50)
print('max-group players:', len(sub_group))
print('max-group winPlacePerc:', sub_group['winPlacePerc'].unique())
print('-'*50)
print('winPlacePerc:', subset['winPlacePerc'].sort_values().unique())



print()
#plot player
group = train.groupby(['matchId','groupId','matchType'])['Id'].count().to_frame('players').reset_index()
group.loc[group['players']>4, 'players'] = 'default' #more than 4 people
group['players'] = group['players'].astype(str)

fig, ax = plt.subplots(1,3,figsize=(16,4))
for mt,ax in zip(['solo','duo','squad'], ax.ravel()):
    ax.set_xlabel(mt)
    group[group['matchType'] == mt]['players'].value_counts().sort_index().plot.bar(ax=ax)
plt.pause(15)


print()
#matchDuration
fig, ax = plt.subplots(1,2,figsize=(12,4))
train['matchDuration'].hist(bins=50,ax=ax[0])
train.query('matchDuration >= 1400 & matchDuration <= 1800')['matchDuration'].hist(bins=50,ax=ax[1])
plt.pause(15)

print()
#min matchDuration
print(train[train['matchDuration'] == train['matchDuration'].min()].head())

print()
#max matchDuration
print(train[train['matchDuration'] == train['matchDuration'].max()].head())

print()
#each match duration always same
duartion_res = (train.groupby('matchId')['matchDuration'].nunique()>1).any()
print(duartion_res)


print()
#boosts and heals
fig, ax = plt.subplots(2,2,figsize=(16,8))
cols = ['boosts','heals']
for cols, ax in zip(cols, ax):
    sub = train[['winPlacePerc', cols]].copy()
    mv = (sub[cols].max() // 5)+1
    sub[cols] = pd.cut(sub[cols], [5*x for x in range(0, mv)], right=False)
    sub.groupby(cols).mean()['winPlacePerc'].plot.bar(ax=ax[0])
    train[cols].hist(bins=20, ax=ax[1])
plt.pause(15)



print()
#revives
print('solo player no revives:', 'solo' in train.query('revives > 0')['matchType'].unique())


print()
#revives hist
fig, ax = plt.subplots(1,2,figsize=(16,4))
col = 'revives'
sub = train.loc[~train['matchType'].str.contains('solo'),['winPlacePerc',col]].copy()
sub[col] = pd.cut(sub[col], [5*x for x in range(0,8)], right=False)
sub.groupby(col).mean()['winPlacePerc'].plot.bar(ax=ax[0])
train[col].hist(bins=20,ax=ax[1])
plt.pause(15)


print()
#killPlace
print(train.groupby(['matchType'])['killPlace'].describe()[['min','mean','max']])

print()
#killPlace hist
plt.figure(figsize=(8,4))
col = 'killPlace'
sub = train[['winPlacePerc', col]].copy()
sub[col] = pd.cut(sub[col], [10*x for x in range(0,11)],right=False)
sub.groupby(col).mean()['winPlacePerc'].plot.bar()
plt.pause(15)


print()
#killPlace is sorted ranking of kills and winPlacePerc in each match
subMatch = train[train['matchId'] == train['matchId'].min()].sort_values(['winPlacePerc','killPlace'])
cols = ['groupId', 'kills', 'winPlacePerc', 'killPlace']
killPlace_res = subMatch[cols]
print(killPlace_res)


print()
#kills
fig, ax = plt.subplots(1,2, figsize=(16,4))
col = 'kills'
sub = train[['winPlacePerc',col]].copy()
sub[col] = pd.cut(sub[col], [5*x for x in range(0,20)],right=False)
sub.groupby(col).mean()['winPlacePerc'].plot.bar(ax=ax[0])
train[train['kills'] <20][col].hist(bins=20, ax=ax[1])
plt.pause(15)


print()
#kill summary of match
sub = train['matchType'].str.contains('solo')
kill_summary_res = pd.concat([train.loc[sub].groupby('matchId')['kills'].sum().describe(), train.loc[~sub].groupby('matchId')['kills'].sum().describe()],
          keys=['solo', 'group'], axis=1).T
print(kill_summary_res)



print()
#killStreaks, DBNOs
fig, ax = plt.subplots(2, 2, figsize=(16,8))
cols = ['killStreaks', 'DBNOs']
for col, ax in zip(cols, ax):
    sub = train[['winPlacePerc', col]].copy()
    sub[col]=pd.cut(sub[col], 6)
    sub.groupby(col).mean()['winPlacePerc'].plot.bar(ax=ax[0])
    train[col].hist(bins=20, ax=ax[1])
plt.pause(15)


print()
#headshotKills, roadKills, teamKills
fig,ax = plt.subplots(3,2,figsize=(16,12))
cols = ['headshotKills', 'roadKills', 'teamKills']
for col, ax in zip(cols, ax):
    sub = train[['winPlacePerc',col]].copy()
    sub.loc[sub[col] >= 5, col] = '5+'
    sub[col] = sub[col].astype(str)
    sub.groupby(col).mean()['winPlacePerc'].plot.bar(ax=ax[0])
    train[col].hist(bins=20, ax=ax[1])
plt.pause(15)



print()
#assists
fig, ax = plt.subplots(1,2, figsize=(16,4))
col='assists'
sub = train[['winPlacePerc', col]].copy()
sub.loc[sub[col] >= 5, col] = '5+'
sub[col] = sub[col].astype(str)
sub.groupby(col).mean()['winPlacePerc'].plot.bar(ax=ax[0])
train[col].hist(bins=20, ax=ax[1])
plt.pause(15)


print()
#number of assists
assists_res = pd.concat([train[train['matchType'] == 'solo'].describe()['assists'], train[train['matchType'] != 'solo'].describe()['assists']], keys=['solo', 'group'], axis=1).T
print(assists_res)



print()
#longestKill
fig, ax = plt.subplots(1,2, figsize=(16, 4))
col = 'longestKill'
sub = train[['winPlacePerc', col]].copy()
sub[col] = pd.cut(sub[col], 6)
sub.groupby(col).mean()['winPlacePerc'].plot.bar(ax=ax[0])
train[col].hist(bins=20, ax=ax[1])
plt.pause(15)



print()
fig, ax = plt.subplots(1,2, figsize=(16,4))
col = 'damageDealt'
sub = train[['winPlacePerc', col]].copy()
sub[col] = pd.cut(sub[col], 6)
sub.groupby(col).mean()['winPlacePerc'].plot.bar(ax=ax[0])
train[col].hist(bins=20, ax=ax[1])
plt.pause(15)


print()
#summary of damageDealt
damageDealt_res = train.query('damageDealt == 0 & (kills >0 | DBNOs >0)')[['damageDealt', 'kills', 'DBNOs', 'headshotKills', 'roadKills', 'teamKills']].head(20)



print()
#walkDistance, rideDistance, swimDistance
fig, ax = plt.subplots(3,2, figsize=(16,12))
cols = ['walkDistance', 'rideDistance', 'swimDistance']
for col, ax in zip(cols, ax):
    sub = train[['winPlacePerc', col]].copy()
    sub[col] = pd.cut(sub[col], 6)
    sub.groupby(col).mean()['winPlacePerc'].plot.bar(ax=ax[0])
    train[col].hist(bins=20, ax=ax[1])
plt.pause(15)



print()
#number of walkDistance, rideDistance, swimDistance
sub = train[['walkDistance', 'rideDistance', 'swimDistance', 'winPlacePerc']].copy()
walk = train['walkDistance']
sub['walkDistanceBin'] = pd.cut(walk, [0, 0.001, walk.quantile(.25), walk.quantile(.5), walk.quantile(.75), 99999])
sub['rideDistanceBin'] = (train['rideDistance'] > 0).astype(int)
sub['swimDistanceBin'] = (train['swimDistance'] > 0).astype(int)

fig,ax = plt.subplots(1, 3, figsize=(16,3), sharey=True)
sub.groupby('walkDistanceBin').mean()['winPlacePerc'].plot.bar(ax=ax[0])
sub.groupby('rideDistanceBin').mean()['winPlacePerc'].plot.bar(ax=ax[1])
sub.groupby('swimDistanceBin').mean()['winPlacePerc'].plot.bar(ax=ax[2])
del sub, walk
plt.pause(15)


print()
#zombie
sub = train.query('walkDistance == 0 & kills == 0 & weaponsAcquired == 0 & \'solo\' in matchType')
print('count:', len(sub), 'winPlacePerc:', round(sub['winPlacePerc'].mean(),3))


print()
#kills summary
kills_res = train.query('kills >3 & (headshotKills/kills) >= 0.8')
print('kills >3 & (headshotKills/kills) >= 0.8')
print('count: ', len(kills_res))
print('winPlacePerc: ', round(kills_res['winPlacePerc'].mean(),3))



print()
#killPoints, rankPoints, winPoints
fig, ax = plt.subplots(1,3, figsize=(16,4))
cols = ['killPoints', 'rankPoints', 'winPoints']
for col, ax in zip(cols, ax.ravel()):
    train.plot.scatter(x=col, y='winPlacePerc', ax=ax)
plt.pause(15)


print()
#winPlacePerc
winPlacePerc_summary = train['winPlacePerc'].describe()
print(winPlacePerc_summary)


print()
#unique match count
print('unique match count: ', train['matchId'].nunique())
maxPlacePerc = train.groupby('matchId')['winPlacePerc'].max() #not contain 1st place
print('match [not contain 1st place]: ', len(maxPlacePerc[maxPlacePerc != 1]))
del maxPlacePerc
#edge case
sub = train[(train['maxPlace'] > 1) & (train['numGroups'] == 1)]
print('match [maxPlace >1 & numGroup == 1] : ', len(sub.groupby('matchId')))
print(' - unique winPlacePerc: ', sub['winPlacePerc'].unique())



print()
winPlace_res = pd.concat([train[train['winPlacePerc'] == 1].head(10), train[train['winPlacePerc'] == 0].head(10)], keys=['winPlacePerc_1', 'winPlacePerc+0'])
print(winPlace_res)



print()
cols = ['kills', 'teamKills', 'DBNOs', 'revives', 'assists', 'boosts', 'heals', 'damageDealt', 'walkDistance', 'rideDistance', 'swimDistance', 'weaponsAcquired']

aggs = ['count', 'min', 'mean', 'max']
#summary of solo match
grp = train.loc[train['matchType'].str.contains('solo')].groupby('matchId')
grpSolo = grp[cols].sum()
#summary of team match
grp = train.loc[~train['matchType'].str.contains('solo')].groupby('matchId')
grpTeam = grp[cols].sum()
winPlacePerc_res = pd.concat([grpSolo.describe().T[aggs], grpTeam.describe().T[aggs]],keys=['solo','team'],axis=1)
print(winPlacePerc_res)


print()
print(grpSolo.nlargest(5,'kills'))

print()
print(grpTeam.nlargest(5,'kills'))

del grpSolo, grpTeam


print()
#group summary
cols = ['kills', 'teamKills', 'DBNOs', 'revives', 'assists', 'boosts', 'heals', 'damageDealt', 'walkDistance', 'rideDistance', 'swimDistance', 'weaponsAcquired']
cols.extend(['killPlace', 'winPlacePerc'])
group = train.groupby(['matchId', 'groupId'])[cols]
fig, ax = plt.subplots(3, 1, figsize=(12,18), sharey=True)
for df, ax in zip([group.mean(), group.min(), group.max()], ax.ravel()):
    sns.heatmap(df.corr(), annot=True, linewidths=.6, fmt='.2f', vmax=1, vmin=-1, center=0, cmap='Blues', ax=ax)
plt.pause(150)



print()
#print match stats
def printMatchStats(matchIds):
    for mid in matchIds:
        subMatch = train[train['matchId'] == mid]
        print('matchType:', subMatch['matchType'].values[0])

        grp1st = subMatch[subMatch['winPlacePerc'] == 1]
        grpOther = subMatch[subMatch['winPlacePerc'] != 1]
        print('players'.ljust(10), ' total:{:>3} 1st:{:>3} other:{:>3}'.format(len(subMatch), len(grp1st), len(grpOther)))
        for c in ['kills', 'teamKills', 'roadKills', 'DBNOs', 'revives', 'assists']:
              print(c.ljust(10), ' total:{:>3} 1st:{:>3} other:{:>3}'.format(subMatch[c].sum(), grp1st[c].sum(), grpOther[c].sum()))
              print('-'*50)

print()


match = train.groupby(['matchId'])['Id'].count()
fullplayer = match[match==100].reset_index()
sampleMid = fullplayer['matchId'][0:5]
printMatchStats(sampleMid)


print()
all_data = train.append(test, sort=False).reset_index(drop=True)
del train, test
#gc.collect()
print(gc.collect())

print()
#reconstruct data
match = all_data.groupby('matchId')
all_data['killsPerc'] = match['kills'].rank(pct=True).values
all_data['killPlacePerc'] = match['killPlace'].rank(pct=True).values
all_data['walkDistancePerc'] = match['walkDistance'].rank(pct=True).values
all_data['walkPerc_killPerc'] = all_data['walkDistancePerc']/all_data['killsPerc']


print()
all_data['_totalDistance'] = all_data['rideDistance'] + all_data['walkDistance'] + all_data['swimDistance']

print()
#fill new feature
def fillInfo(df, val):
    numcols = df.select_dtypes(include='number').columns
    cols = numcols[numcols != 'winPlacePerc']
    df[df == np.Inf] = np.NaN
    df[df == np.NINF] = np.NaN
    for c in cols:
        df[c].fillna(val,inplace=True)


print()
#create new feature
all_data['_healthItems'] = all_data['heals'] + all_data['boosts']
all_data['_headshotKillRate'] = all_data['headshotKills']/all_data['kills']
all_data['_killPlaceOverMaxPlace'] = all_data['killPlace'] / all_data['maxPlace']
all_data['_killsOverWalkDistance'] = all_data['kills'] / all_data['walkDistance']
all_data['_killsOverDistance'] = all_data['kills'] / all_data['_totalDistance']
all_data['_walkDistancePerSec'] = all_data['walkDistance'] / all_data['matchDuration']
fillInfo(all_data,0)


print()
#drop feature
all_data.drop(['boosts', 'heals', 'killStreaks', 'DBNOs'], axis=1, inplace=True)
all_data.drop(['headshotKills','roadKills', 'vehicleDestroys'], axis=1, inplace=True)
all_data.drop(['rideDistance','swimDistance', 'matchDuration'], axis=1, inplace=True)
all_data.drop(['rankPoints','killPoints', 'winPoints'], axis=1, inplace=True)


print()
#group the data
match = all_data.groupby(['matchId'])
group = all_data.groupby(['matchId', 'groupId', 'matchType'])
agg_col = list(all_data.columns)
exclude_agg_col = ['Id','matchId','groupId','matchType','maxPlace','numGroups','winPlacePerc']
for c in exclude_agg_col:
    agg_col.remove(c)
print(agg_col)
sum_col = ['kills','killPlace','damageDealt','walkDistance','_healthItems']


print()
match_data = pd.concat([match.size().to_frame('m.players'),
                        match[sum_col].sum().rename(columns=lambda s: 'm.sum.' + s),
                        match[sum_col].max().rename(columns=lambda s: 'm.max.' + s),
                        match[sum_col].mean().rename(columns=lambda s: 'm.mean.' + s)], axis=1).reset_index()
match_data = pd.merge(match_data,group[sum_col].sum().rename(columns=lambda s: 'sum.' + s).reset_index())
match_data = reduce_mem_usage(match_data)

print(match_data.shape)


print()
#ranking kill and killPlace
minKills= all_data.sort_values(['matchId','groupId','kills','killPlace']).groupby(['matchId','groupId','kills']).first().reset_index().copy()
for n in np.arange(4):
    c = 'kills_' + str(n) +'_Place'
    nKills = (minKills['kills'] == n)
    minKills.loc[nKills, c] = minKills[nKills].groupby(['matchId'])['killPlace'].rank().values
    match_data = pd.merge(match_data, minKills[nKills][['matchId','groupId',c]],how='left')

match_data = reduce_mem_usage(match_data)
del minKills,nKills
print()
print(match_data.shape)

print()
print(match_data.head())


print()
#mean, max, min
all_data = pd.concat([group.size().to_frame('players'),
                      group.mean(),
                      group[agg_col].max().rename(columns=lambda s: 'max.' +s),
                      group[agg_col].min().rename(columns=lambda s: 'min.' +s)], axis=1).reset_index()
all_data = reduce_mem_usage(all_data)
print(all_data)


print()
#aggregate feature
numcols = all_data.select_dtypes(include='number').columns.values
numcols = numcols[numcols != 'winPlacePerc']

all_data = pd.merge(all_data,match_data)
del match_data
gc.collect()

all_data['enemy.players'] = all_data['m.players'] - all_data['players']
for c in sum_col:
    all_data['enemy.players'+c] = (all_data['m.sum.'+c]- all_data['sum.'+c])/all_data['enemy.players']
    all_data['p.sum_msum.'+c] = all_data['m.sum.'+c] / all_data['m.sum.'+c]
    all_data['p.max_mmean.'+c] = all_data['max.'+c] / all_data['m.mean.'+c]
    all_data['p.max_msum.'+c] = all_data['max.'+c] / all_data['m.sum.'+c]
    all_data['p.max_mmax.'+c] = all_data['max.'+c] / all_data['m.max.'+c]
    all_data.drop(['m.sum.'+c, 'm.max.'+c], axis=1, inplace=True)
fillInfo(all_data,0)
print(all_data.shape)


print()
match = all_data.groupby('matchId')
matchRank = match[numcols].rank(pct=True).rename(columns=lambda s:'rank.'+s)
all_data = reduce_mem_usage(pd.concat([all_data,matchRank],axis=1))
rank_col = matchRank.columns
del matchRank
gc.collect()

match = all_data.groupby('matchId')
matchRank = match[rank_col].max().rename(columns=lambda s:'max.'+s).reset_index()
all_data = pd.merge(all_data,matchRank)
for c in numcols:
    all_data['rank.'+c] = all_data['rank.'+c] / all_data['max.rank.'+c]
    all_data.drop(['max.rank.'+c], axis=1,inplace=True)
del matchRank
gc.collect()
print(all_data.shape)


print()
#encode
#all_data['matchType'] = all_data['matchType'].apply(mapper)

all_data = pd.concat([all_data,pd.get_dummies(all_data['matchType'])], axis=1)
all_data.drop(['matchType'], axis=1, inplace=True)
all_data['matchId'] = all_data['matchId'].apply(lambda x: int(x,16))
all_data['groupId'] = all_data['groupId'].apply(lambda x: int(x,16))

null_count = all_data.isnull().sum().sort_values()
print(null_count[null_count>0])

cols = [col for col in all_data.columns if col not in ['Id','matchId','groupId']]
for i,t in all_data.loc[:,cols].dtypes.iteritems():
    if t == object:
        all_data[i] = pd.factorize(all_data[i])[0]

all_data = reduce_mem_usage(all_data)
all_data.head()

print()
#predict
X_train = all_data[all_data['winPlacePerc'].notnull()].reset_index(drop=True)
X_test = all_data[all_data['winPlacePerc'].isnull()].drop(['winPlacePerc'], axis=1).reset_index(drop=True)
del all_data
gc.collect()

Y_train = X_train.pop('winPlacePerc')
X_test_group = X_test[['matchId','groupId']].copy()
train_matchId = X_train['matchId']

X_train.drop(['matchId','groupId'], axis=1, inplace=True)
X_test.drop(['matchId','groupId'], axis=1, inplace=True)
print(X_train.shape, X_test.shape)

print(pd.DataFrame([[val for val in dir()], [sys.getsizeof(eval(val)) for val in dir()]],
                   index=['name','size']).T.sort_values('size', ascending=False).reset_index(drop=True)[:10])
              


print()
params = {'learning_rate': 0.05, 'objective': 'mae', 'metric':'mae', 'num_leaves': 128,
    'verbose': 1, 'verbose': 1, 'bagging_fraction': 0.7, 'feature_fraction': 0.7
}

reg = lgb.LGBMRegressor(**params, n_estimators=10000)
reg.fit(X_train, Y_train)
pred = reg.predict(X_test, num_iteration=reg.best_iteration_)

# Plot feature importance
feature_importance = reg.feature_importances_
feature_importance = 100.0 * (feature_importance / feature_importance.max())
sorted_idx = np.argsort(feature_importance)
sorted_idx = sorted_idx[len(feature_importance) - 30:]
pos = np.arange(sorted_idx.shape[0]) + .5

plt.figure(figsize=(12,8))
plt.barh(pos, feature_importance[sorted_idx], align='center')
plt.yticks(pos, X_train.columns[sorted_idx])
plt.xlabel('Relative Importance')
plt.title('Variable Importance')
plt.show()

print()
print(X_train.columns[np.argsort(-feature_importance)].values)

X_test_group['_nofit.winPlacePerc'] = pred
group = X_test_group.groupby(['matchId'])
X_test_group['winPlacePerc'] = pred
X_test_group['_rank.winPlacePerc'] = group['winPlacePerc'].rank(method='min')
X_test = pd.concat([X_test, X_test_group], axis=1)

fullgroup = (X_test['numGroups'] == X_test['maxPlace'])
subset = X_test.loc[fullgroup]
X_test.loc[fullgroup, 'winPlacePerc'] = (subset['_rank.winPlacePerc'].values - 1) / (subset['maxPlace'].values - 1)

subset = X_test.loc[~fullgroup]
gap = 1.0 / (subset['maxPlace'].values - 1)
new_perc = np.around(subset['winPlacePerc'].values / gap) * gap
X_test.loc[~fullgroup, 'winPlacePerc'] = new_perc

X_test['winPlacePerc'] = X_test['winPlacePerc'].clip(lower=0,upper=1)

# edge cases
X_test.loc[X_test['maxPlace'] == 0, 'winPlacePerc'] = 0
X_test.loc[X_test['maxPlace'] == 1, 'winPlacePerc'] = 1
X_test.loc[(X_test['maxPlace'] > 1) & (X_test['numGroups'] == 1), 'winPlacePerc'] = 0
print(X_test['winPlacePerc'].describe())


#submittion
test = pd.read_csv('input/test_V2.csv')
test['matchId'] = test['matchId'].apply(lambda x: int(x,16))
test['groupId'] = test['groupId'].apply(lambda x: int(x,16))

submission = pd.merge(test, X_test[['matchId','groupId','winPlacePerc']])
submission = submission[['Id','winPlacePerc']]
submission.to_csv("submission.csv", index=False)


